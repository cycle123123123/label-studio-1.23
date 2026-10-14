"""Convert a project's imported annotations into pre-annotations (predictions).

Part of the cross-validation workflow (same-task multi-annotator route):
the editor change prefers selecting the task prediction when the user has no
annotation of their own, so predictions act as the prefill source and every
annotator's Submit creates their own annotation. The imported annotation rows
themselves are removed afterwards (make a backup first!):
  - without this, a fresh annotator would open someone else's annotation and
    the old editor logic would overwrite it;
  - predictions keep the imported values visible and editable-as-a-copy.

Use with a fresh import (before real human annotations exist). The script is
idempotent: existing `prelabel` predictions are updated in place.

Usage (from the label_studio directory, PYTHONPATH pointing at label_studio):
  python ../scripts/make_cross_prelabels.py --project-id 1 --dry-run
  python ../scripts/make_cross_prelabels.py --project-id 1            # convert only
  python ../scripts/make_cross_prelabels.py --project-id 1 --delete-source --yes
                                                                # convert + delete imported annotations
"""

import argparse
import os
import sys
import uuid

import django

DEFAULT_SETTINGS = os.environ.get('DJANGO_SETTINGS_MODULE', 'core.settings.label_studio')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', DEFAULT_SETTINGS)

PRELABEL_VERSION = 'prelabel'


def parse_args():
    parser = argparse.ArgumentParser(description='Convert imported annotations into prelabel predictions')
    parser.add_argument('--project-id', type=int, required=True)
    parser.add_argument(
        '--delete-source',
        action='store_true',
        help='Delete the source annotations after conversion (DESTRUCTIVE - backup first)',
    )
    parser.add_argument('--yes', action='store_true', help='Confirm the destructive step')
    parser.add_argument('--dry-run', action='store_true', help='Print statistics only')
    return parser.parse_args()


def to_prediction_results(result):
    converted = []
    for item in result or []:
        if not isinstance(item, dict):
            continue
        clean = {key: value for key, value in item.items() if key not in ('id', 'origin', 'hidden', 'meta')}
        clean['id'] = uuid.uuid4().hex[:10]
        converted.append(clean)
    return converted


def main():
    args = parse_args()
    django.setup()

    from projects.models import Project
    from tasks.models import Annotation, Prediction, Task

    project = Project.objects.get(pk=args.project_id)
    tasks = list(Task.objects.filter(project=project).order_by('inner_id', 'id'))

    converted = updated = skipped_empty = already = 0

    for task in tasks:
        # Richest source annotation (imported rows may carry a stale result_count).
        annotations = sorted(
            (a for a in task.annotations.all() if not a.was_cancelled),
            key=lambda a: (len(a.result or []), a.id),
            reverse=True,
        )
        if not annotations:
            skipped_empty += 1
            continue

        prediction_results = to_prediction_results(annotations[0].result)
        if not prediction_results:
            skipped_empty += 1
            continue

        if args.dry_run:
            converted += 1
            continue

        prediction = Prediction.objects.filter(task=task, model_version=PRELABEL_VERSION).first()
        if prediction is None:
            Prediction.objects.create(
                task=task,
                project=project,
                model_version=PRELABEL_VERSION,
                score=1.0,
                result=prediction_results,
            )
            converted += 1
        else:
            prediction.result = prediction_results
            prediction.score = 1.0
            prediction.save(update_fields=['result', 'score', 'updated_at'])
            updated += 1
            already += 1

    print(f'Project            : {project.id} - {project.title}')
    print(f'Tasks              : {len(tasks)}')
    print(f'Predictions created: {converted}')
    print(f'Predictions updated: {updated}')
    print(f'Tasks skipped (no annotation content): {skipped_empty}')

    if args.dry_run:
        print('Dry run: nothing written')
        return 0

    if args.delete_source:
        if not args.yes:
            print('Refusing to delete without --yes')
            return 1
        deleted, _ = Annotation.objects.filter(project=project).delete()
        print(f'Deleted annotations: {deleted}')
    else:
        print('Source annotations kept (pass --delete-source --yes to remove them)')

    return 0


if __name__ == '__main__':
    sys.exit(main())
