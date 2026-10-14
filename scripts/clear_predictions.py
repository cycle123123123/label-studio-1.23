"""Clear (or delete) a project's predictions - typically the `prelabel` rows created
from imported annotations, when annotators must start from a blank canvas.

Keeps annotations, tasks and assignments untouched.

Usage (from the label_studio directory, PYTHONPATH pointing at label_studio):
  python ../scripts/clear_predictions.py --project-id 1 --dry-run
  python ../scripts/clear_predictions.py --project-id 1 --yes                # empty the result, keep the row
  python ../scripts/clear_predictions.py --project-id 1 --yes --mode delete  # remove the prediction rows
  python ../scripts/clear_predictions.py --project-id 1 --yes --task-ids 5010,5015-5020
"""

import argparse
import os
import sys

import django

DEFAULT_SETTINGS = os.environ.get('DJANGO_SETTINGS_MODULE', 'core.settings.label_studio')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', DEFAULT_SETTINGS)


def parse_args():
    parser = argparse.ArgumentParser(description='Clear project predictions')
    parser.add_argument('--project-id', type=int, required=True)
    parser.add_argument('--model-version', default='prelabel', help='Only touch predictions with this model_version')
    parser.add_argument('--all-versions', action='store_true', help='Ignore --model-version and touch every prediction')
    parser.add_argument('--task-ids', default='', help='Limit to these task ids / ranges, e.g. 5010,5015-5020')
    parser.add_argument('--mode', choices=['empty', 'delete', 'filter'], default='empty',
                        help='empty = result set to [] , delete = remove rows, filter = keep only matching results')
    parser.add_argument('--keep-types', default='', help='With --mode filter: keep only these result types, e.g. rectanglelabels')
    parser.add_argument('--keep-labels', default='',
                        help='With --mode filter: keep only boxes carrying these labels (comma separated)')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--yes', action='store_true', help='Confirm the write')
    return parser.parse_args()


def parse_task_ids(value):
    ids = []
    for token in str(value).replace(' ', '').split(','):
        if not token:
            continue
        if '-' in token:
            start, end = token.split('-')
            ids.extend(range(int(start), int(end) + 1))
        else:
            ids.append(int(token))
    return ids


def main():
    args = parse_args()
    django.setup()

    from projects.models import Project
    from tasks.models import Prediction

    project = Project.objects.get(pk=args.project_id)
    queryset = Prediction.objects.filter(project=project)
    if not args.all_versions:
        queryset = queryset.filter(model_version=args.model_version)
    task_ids = parse_task_ids(args.task_ids)
    if task_ids:
        queryset = queryset.filter(task_id__in=task_ids)

    total = queryset.count()
    with_result = queryset.exclude(result=[]).count()
    keep_types = {t.strip() for t in args.keep_types.split(',') if t.strip()}
    keep_labels = {l.strip() for l in args.keep_labels.split(',') if l.strip()}
    print(f'Project                 : {project.id} - {project.title}')
    print(f'Model version filter    : {"(all)" if args.all_versions else args.model_version}')
    print(f'Task filter             : {task_ids[:10]}{"..." if len(task_ids) > 10 else ""}' if task_ids else 'Task filter             : (all tasks)')
    print(f'Predictions matched     : {total}')
    print(f'  with non-empty result : {with_result}')
    print(f'Mode                    : {args.mode}')
    if args.mode == 'filter':
        print(f'  keep types            : {sorted(keep_types) or "(any)"}')
        print(f'  keep labels           : {sorted(keep_labels) or "(any)"}')

    if args.dry_run:
        print('Dry run: nothing written')
        return 0

    if not args.yes:
        print('Refusing to write without --yes')
        return 1

    if args.mode == 'delete':
        deleted, _ = queryset.delete()
        remaining = Prediction.objects.filter(project=project).count()
        print(f'Deleted {deleted} predictions. Remaining in project: {remaining}')
    elif args.mode == 'filter':
        updated = 0
        samples = []
        for prediction in queryset.iterator():
            kept = []
            for result in prediction.result or []:
                if keep_types and result.get('type') not in keep_types:
                    continue
                labels = set(result.get('value', {}).get('rectanglelabels') or [])
                if keep_labels and not (labels & keep_labels):
                    continue
                kept.append(result)
            if len(samples) < 3:
                samples.append((prediction.task_id, len(prediction.result or []), len(kept)))
            if kept != (prediction.result or []):
                prediction.result = kept
                prediction.save(update_fields=['result', 'updated_at'])
                updated += 1
        print(f'Filtered {updated} predictions; samples (task, before -> after): {samples}')
    else:
        updated = queryset.update(result=[])
        print(f'Emptied result of {updated} predictions')

    # keep the per-task prediction counter in sync
    from tasks.models import Task

    affected_ids = task_ids or list(queryset.values_list('task_id', flat=True))
    for task_id in set(affected_ids):
        count = Prediction.objects.filter(task_id=task_id).count()
        Task.objects.filter(id=task_id).update(total_predictions=count)

    return 0


if __name__ == '__main__':
    sys.exit(main())
