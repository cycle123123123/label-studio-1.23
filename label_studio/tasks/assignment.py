"""Helpers for manual task assignment flow in OSS."""

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q


def has_manual_assignment(project) -> bool:
    """Return True when at least one task in project is manually assigned."""
    from tasks.models import TaskAssignment

    return TaskAssignment.objects.filter(task__project=project).exists()


def _is_privileged_assignment_user(project, user) -> bool:
    if user is None or not user.is_authenticated:
        return False

    return bool(user.id == project.created_by_id or user.is_staff or user.is_superuser)


def can_manage_assignments(project, user) -> bool:
    return _is_privileged_assignment_user(project, user)


def is_assignment_enforced_for_user(project, user) -> bool:
    """Return True when user should only work with explicitly assigned tasks."""
    if _is_privileged_assignment_user(project, user):
        return False

    # This project uses strict manual assignment: ordinary users cannot enter
    # the automatic queue and must have an explicit task assignment.
    return True


def filter_tasks_for_user_assignments(queryset, project, user):
    """
    Restrict queryset to current user's assigned tasks when manual assignment mode is active.

    Returns filtered queryset and the enforcement flag.
    """
    if not is_assignment_enforced_for_user(project, user):
        return queryset, False

    return queryset.filter(assignments__user=user), True


def can_user_access_task(task, user) -> bool:
    """Check direct access to task object under assignment policy."""
    if task is None or user is None or not user.is_authenticated:
        return False

    # Direct task endpoints must use the same active-organization boundary as
    # project list endpoints. An old TaskAssignment must not keep access alive
    # after a member is removed or switches to another organization.
    # Projects without an organization (legacy/FSM cold-start projects) skip the boundary.
    if (
        task.project.organization_id
        and user.active_organization_id
        and task.project.organization_id != user.active_organization_id
    ):
        return False

    if not is_assignment_enforced_for_user(task.project, user):
        return True

    from organizations.models import OrganizationMember

    if not OrganizationMember.objects.filter(
        user_id=user.id,
        organization_id=task.project.organization_id,
        deleted_at__isnull=True,
    ).exists():
        return False

    return task.assignments.filter(user_id=user.id).exists()


def filter_task_related_queryset_for_user(queryset, user, project_lookup='project', task_lookup='task'):
    """Restrict annotation-like querysets to the active organization and assigned tasks."""
    if user is None or not user.is_authenticated:
        return queryset.none()

    queryset = queryset.filter(**{f'{project_lookup}__organization': user.active_organization})
    if user.is_staff or user.is_superuser:
        return queryset

    return queryset.filter(
        Q(**{f'{project_lookup}__created_by_id': user.id})
        | Q(**{f'{task_lookup}__assignments__user_id': user.id})
    ).distinct()


def get_assignable_users(project):
    """Users from project organization available in assignment form."""
    User = get_user_model()
    if not project.organization_id:
        return User.objects.none()

    member_ids = project.organization.members.filter(deleted_at__isnull=True).values_list('user_id', flat=True)
    return User.objects.filter(id__in=member_ids, is_active=True).order_by('email')


def apply_task_assignments(project, task_ids, assignee_ids, assigned_by):
    """
    Apply assignment/unassignment for provided task ids and append audit records.

    Multi-assignee semantics: a task can hold several assignments at once
    (cross-validation labeling). For each task:
      - users in assignee_ids without an assignment -> created
      - users in assignee_ids already assigned      -> unchanged
      - users assigned but not in assignee_ids      -> removed
    An empty (or [0]) assignee_ids list removes all assignments.

    Returns dict with changed items counters.
    """
    from tasks.models import Task, TaskAssignment, TaskAssignmentAuditLog

    if not task_ids:
        return {'changed': 0, 'assigned': 0, 'removed': 0}

    # Normalize: accept a single int (legacy callers) or a list; treat [0]/[] as
    # "unassign all", drop other non-positive ids.
    if isinstance(assignee_ids, int):
        assignee_ids = [assignee_ids]
    assignee_ids = [uid for uid in (assignee_ids or []) if isinstance(uid, int) and uid != 0]
    unassign_all = not assignee_ids

    with transaction.atomic():
        # Lock the task rows before reading assignments. This also serializes
        # first-time assignments, where no TaskAssignment row exists yet.
        valid_task_ids = list(
            Task.objects.select_for_update()
            .filter(project=project, id__in=task_ids)
            .order_by('id')
            .values_list('id', flat=True)
        )
        if not valid_task_ids:
            return {'changed': 0, 'assigned': 0, 'removed': 0}

        assignments = (
            TaskAssignment.objects.select_for_update()
            .filter(task_id__in=valid_task_ids)
            .select_related('user')
        )
        existing_by_task_id = {}
        for assignment in assignments:
            existing_by_task_id.setdefault(assignment.task_id, []).append(assignment)

        to_create = []
        to_delete_ids = []
        audit_logs = []
        assigned_count = 0
        removed_count = 0

        for task_id in valid_task_ids:
            current = existing_by_task_id.get(task_id, [])
            current_user_ids = {assignment.user_id for assignment in current}

            if unassign_all:
                target_user_ids = set()
            else:
                target_user_ids = set(assignee_ids)

            # Remove assignments not in the target list.
            for assignment in current:
                if assignment.user_id not in target_user_ids:
                    to_delete_ids.append(assignment.id)
                    removed_count += 1
                    audit_logs.append(
                        TaskAssignmentAuditLog(
                            project_id=project.id,
                            task_id=task_id,
                            action=TaskAssignmentAuditLog.ACTION_UNASSIGNED,
                            assignee=None,
                            previous_assignee_id=assignment.user_id,
                            assigned_by_id=getattr(assigned_by, 'id', None),
                        )
                    )

            # Create assignments for target users not yet assigned.
            for user_id in assignee_ids:
                if user_id in current_user_ids:
                    continue
                assigned_count += 1
                to_create.append(TaskAssignment(task_id=task_id, user_id=user_id, assigned_by=assigned_by))
                audit_logs.append(
                    TaskAssignmentAuditLog(
                        project_id=project.id,
                        task_id=task_id,
                        action=TaskAssignmentAuditLog.ACTION_ASSIGNED,
                        assignee_id=user_id,
                        previous_assignee=None,
                        assigned_by=assigned_by,
                    )
                )

        if to_delete_ids:
            TaskAssignment.objects.filter(id__in=to_delete_ids).delete()
        if to_create:
            TaskAssignment.objects.bulk_create(to_create, batch_size=1000)
        if audit_logs:
            TaskAssignmentAuditLog.objects.bulk_create(audit_logs, batch_size=1000)

    changed = assigned_count + removed_count
    return {'changed': changed, 'assigned': assigned_count, 'removed': removed_count}
