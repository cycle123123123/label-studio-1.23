"""Assign cross-validation and single-annotator tasks for a Label Studio project.

Cross set  : selected by stride over `inner_id` (default: every 5th, matching the
             local validation run) or by a plain task-id range, and assigned to
             ALL cross users at once (one task -> several assignees).
Rest       : the remaining tasks are distributed round-robin over the single
             annotators, so the whole project can be assigned in one command.

Reuses `tasks.assignment.apply_task_assignments`, so audit logs are written and
re-running is idempotent (already-assigned users are skipped, stale assignees of
the selected tasks are removed - keep --cross-users consistent between runs).

Usage (from the label_studio directory, PYTHONPATH pointing at label_studio):
  python ../scripts/assign_cross_tasks.py --project-id 1 --cross-users 2,3,4 \
      --single-users 2,3 --stride 5 --dry-run
  python ../scripts/assign_cross_tasks.py --project-id 1 --cross-users 2,3,4 --single-users 2,3
  python ../scripts/assign_cross_tasks.py --project-id 1 --cross-users 2,3,4 --cross-range 1-140
"""

import argparse
import os
import sys

import django

DEFAULT_SETTINGS = os.environ.get('DJANGO_SETTINGS_MODULE', 'core.settings.label_studio')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', DEFAULT_SETTINGS)


def parse_args():
    parser = argparse.ArgumentParser(description='Assign cross-validation and single tasks')
    parser.add_argument('--project-id', type=int, required=True)
    parser.add_argument('--cross-users', required=True, help='Comma separated user ids for the cross set')
    parser.add_argument('--single-users', default='', help='Comma separated user ids for the remaining tasks')
    parser.add_argument('--stride', type=int, default=5, help='Take every Nth task by inner_id (default 5)')
    parser.add_argument('--offset', type=int, default=1, help='1-based position of the first sampled task')
    parser.add_argument(
        '--cross-range',
        default='',
        help='Alternative to --stride: plain task-id range like 1-140 (uses the DM “ID” column)',
    )
    parser.add_argument(
        '--single-mode',
        choices=['round_robin', 'chunks'],
        default='round_robin',
        help='How the remaining tasks are split: round_robin (default) or whole chunks',
    )
    parser.add_argument('--chunks', type=int, default=7, help='With --single-mode chunks: how many chunks to cut')
    parser.add_argument(
        '--chunk-ratio',
        default='',
        help='With --single-mode chunks: how many chunks each single user takes, e.g. 3,2,2',
    )
    parser.add_argument('--dry-run', action='store_true', help='Print the plan only')
    return parser.parse_args()


def parse_ids(value):
    return [int(part) for part in str(value).replace(' ', '').split(',') if part]


def parse_range(value):
    start, end = value.split('-')
    return int(start), int(end)


def main():
    args = parse_args()
    django.setup()

    from projects.models import Project
    from tasks.assignment import apply_task_assignments, get_assignable_users
    from tasks.models import Task

    project = Project.objects.get(pk=args.project_id)
    cross_users = parse_ids(args.cross_users)
    single_users = parse_ids(args.single_users)

    tasks = list(Task.objects.filter(project=project).order_by('inner_id', 'id'))
    if not tasks:
        print(f'Project {project.id} has no tasks')
        return 1

    if args.cross_range:
        start, end = parse_range(args.cross_range)
        cross_tasks = [t for t in tasks if start <= t.id <= end]
    else:
        cross_tasks = tasks[max(args.offset - 1, 0) :: max(args.stride, 1)]

    cross_ids = [t.id for t in cross_tasks]
    rest = [t for t in tasks if t.id not in set(cross_ids)]

    valid_users = set(get_assignable_users(project).values_list('id', flat=True))
    unknown = [uid for uid in cross_users + single_users if uid not in valid_users]
    if unknown:
        print(f'Users not assignable in this project: {unknown}')
        print(f'Assignable user ids: {sorted(valid_users)}')
        return 1
    if not single_users and rest:
        print('WARNING: --single-users is empty, the remaining tasks will not be assigned')

    print(f'Project        : {project.id} - {project.title}')
    print(f'Tasks          : {len(tasks)}')
    print(f'Cross set      : {len(cross_ids)} tasks -> users {cross_users}')
    print(
        f'Rest           : {len(rest)} tasks -> users {single_users} '
        f'({"chunks %s ratio %s" % (args.chunks, args.chunk_ratio) if args.single_mode == "chunks" else "round-robin"})'
    )
    if cross_ids:
        print(f'Cross task ids : {cross_ids[:10]}{"..." if len(cross_ids) > 10 else ""}')

    buckets = {uid: [] for uid in single_users}
    if single_users and rest:
        if args.single_mode == 'chunks':
            ratio = parse_ids(args.chunk_ratio)
            if not ratio or sum(ratio) != args.chunks or len(ratio) != len(single_users):
                print(f'--chunk-ratio must cover {args.chunks} chunks over {len(single_users)} users, e.g. 3,2,2')
                return 1
            # cut rest into `chunks` consecutive slices (bigger slices first), then hand
            # each user `ratio[i]` slices in order
            total = len(rest)
            base, extra = divmod(total, args.chunks)
            slices, cursor = [], 0
            for i in range(args.chunks):
                size = base + (1 if i < extra else 0)
                slices.append(rest[cursor : cursor + size])
                cursor += size
            pointer = 0
            for uid, take in zip(single_users, ratio):
                owned = slices[pointer : pointer + take]
                pointer += take
                buckets[uid] = [t.id for chunk in owned for t in chunk]
                print(f'User {uid}: chunks {take} -> {len(buckets[uid])} tasks')
        else:
            for index, task in enumerate(rest):
                buckets[single_users[index % len(single_users)]].append(task.id)

    print('Plan: ' + ' | '.join(f'user {uid}: cross-{len(cross_ids)} + single-{len(buckets[uid])}' for uid in single_users))
    for uid in single_users:
        cross_extra = len(cross_ids) if uid in cross_users else 0
        print(f'  user {uid} total tasks to label: {len(buckets[uid]) + cross_extra}')

    if args.dry_run:
        print('Dry run: nothing written')
        return 0

    stats = apply_task_assignments(project, cross_ids, cross_users, project.created_by)
    print(f'Cross assigned : {stats}')

    for uid, task_ids in buckets.items():
        if not task_ids:
            continue
        part = apply_task_assignments(project, task_ids, [uid], project.created_by)
        print(f'User {uid}: {len(task_ids)} tasks -> {part}')

    return 0


if __name__ == '__main__':
    sys.exit(main())
