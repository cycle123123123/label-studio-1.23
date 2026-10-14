"""Clear a project's annotations so labeling can start over from the prelabels.

Keeps: tasks, predictions (prelabels), task assignments, assignment audit log.
Removes: annotations (task_completion), their drafts, and by default the annotation
         workflow audit log (submitted / updated / skipped) so the statistics
         dashboard and the "标注数" counters start from zero again.

Afterwards task counters and the project summary are recalculated.

Usage (from the label_studio directory, PYTHONPATH pointing at label_studio):
  python ../scripts/reset_project_annotations.py --project-id 1 --dry-run
  python ../scripts/reset_project_annotations.py --project-id 1 --yes
  python ../scripts/reset_project_annotations.py --project-id 1 --yes --keep-workflow-audit
"""

import argparse
import os
import sys
from collections import Counter

import django

DEFAULT_SETTINGS = os.environ.get('DJANGO_SETTINGS_MODULE', 'core.settings.label_studio')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', DEFAULT_SETTINGS)


def parse_args():
    parser = argparse.ArgumentParser(description='Reset a project to "no annotations yet"')
    parser.add_argument('--project-id', type=int, required=True)
    parser.add_argument('--yes', action='store_true', help='Confirm the destructive step')
    parser.add_argument('--dry-run', action='store_true', help='Print what would be removed')
    parser.add_argument(
        '--keep-workflow-audit',
        action='store_true',
        help='Keep the annotation workflow audit log (submitted/updated/skipped)',
    )
    return parser.parse_args()


def main():
    args = parse_args()
    django.setup()

    from django.db import transaction
    from projects.models import Project
    from tasks.functions import update_tasks_counters
    from tasks.models import Annotation, AnnotationDraft, Task, TaskWorkflowAuditLog

    project = Project.objects.get(pk=args.project_id)

    annotations = Annotation.objects.filter(project=project)
    drafts = AnnotationDraft.objects.filter(task__project=project)
    workflow_logs = TaskWorkflowAuditLog.objects.filter(project=project)

    per_annotator = Counter(
        (email or f'user {uid}')
        for uid, email in annotations.values_list('completed_by_id', 'completed_by__email')
    )

    print(f'Project                 : {project.id} - {project.title}')
    print(f'Annotations to delete   : {annotations.count()}')
    for email, count in per_annotator.most_common():
        print(f'    {email}: {count}')
    print(f'Drafts to delete        : {drafts.count()}')
    print(
        f'Workflow audit log rows : {workflow_logs.count()}'
        f'{" (kept)" if args.keep_workflow_audit else " (will be deleted)"}'
    )
    print(f'Tasks (kept)            : {Task.objects.filter(project=project).count()}')
    print('Predictions / assignments are kept untouched')

    if args.dry_run:
        print('Dry run: nothing written')
        return 0

    if not args.yes:
        print('Refusing to delete without --yes')
        return 1

    with transaction.atomic():
        drafts.delete()
        annotations.delete()
        if not args.keep_workflow_audit:
            workflow_logs.delete()

    # Recalculate task counters from scratch: with all annotations gone every task
    # becomes "not labeled" again (predictions do not count as annotations).
    tasks = Task.objects.filter(project=project)
    update_tasks_counters(tasks, from_scratch=True)
    tasks.update(is_labeled=False)

    # Project summary counters (annotation / label counters shown in the UI)
    if hasattr(project, 'summary'):
        project.summary.reset(tasks_data_based=False)

    print('Done: annotations, drafts%s cleared; task counters and summary recalculated'
          % ('' if args.keep_workflow_audit else ' and workflow audit log'))
    print(f'Remaining annotations: {Annotation.objects.filter(project=project).count()}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
