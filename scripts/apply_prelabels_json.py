"""Rebuild a project's pre-annotations (predictions) from a reference import JSON.

The reference file lists tasks with their original annotation content, e.g.
`全部剧照预标注.json` ({"data": {"image": ...}, "annotations": [{"result": [...]}]}).
Tasks are matched by their image URL, so ids may differ between environments.

Typical use: the project's current prelabels carry too much (fields from a previous
round); restore them to the imported state - optionally keeping ONLY the bounding
boxes (e.g. 服饰) and dropping every field that is not a box.

Usage (from the label_studio directory, PYTHONPATH pointing at label_studio):
  python ../scripts/apply_prelabels_json.py --project-id 1 --file /tmp/labels.json --dry-run
  # keep only 服饰 boxes, drop all other fields:
  python ../scripts/apply_prelabels_json.py --project-id 1 --file /tmp/labels.json --boxes-only --keep-labels 服饰 --yes
  # full replace with the file content (all fields):
  python ../scripts/apply_prelabels_json.py --project-id 1 --file /tmp/labels.json --yes
  # only for specific tasks:
  python ../scripts/apply_prelabels_json.py --project-id 1 --file /tmp/labels.json --boxes-only --keep-labels 服饰 --task-ids 5010,5015-5020 --yes
"""

import argparse
import json
import os
import sys

import django

DEFAULT_SETTINGS = os.environ.get('DJANGO_SETTINGS_MODULE', 'core.settings.label_studio')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', DEFAULT_SETTINGS)

PRELABEL_VERSION = 'prelabel'


def parse_args():
    parser = argparse.ArgumentParser(description='Rebuild predictions from a reference JSON')
    parser.add_argument('--project-id', type=int, required=True)
    parser.add_argument('--file', required=True, help='Reference JSON (list of tasks with annotations/predictions)')
    parser.add_argument('--boxes-only', action='store_true', help='Keep only rectanglelabels results, drop other fields')
    parser.add_argument('--keep-labels', default='', help='With --boxes-only: keep only boxes carrying these labels')
    parser.add_argument('--task-ids', default='', help='Limit to task ids / ranges, e.g. 5010,5015-5020')
    parser.add_argument('--model-version', default=PRELABEL_VERSION)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--yes', action='store_true')
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


def reference_results(task):
    """Annotation results from the reference file (annotations first, then predictions)."""
    for key in ('annotations', 'predictions'):
        items = task.get(key) or []
        if items:
            return items[0].get('result') or []
    return []


def main():
    args = parse_args()
    django.setup()

    from projects.models import Project
    from tasks.models import Prediction, Task

    with open(args.file, encoding='utf-8') as fh:
        reference = json.load(fh)
    by_image = {}
    for item in reference:
        image = (item.get('data') or {}).get('image')
        if image:
            by_image[image] = reference_results(item)

    keep_labels = {label.strip() for label in args.keep_labels.split(',') if label.strip()}
    task_id_filter = parse_task_ids(args.task_ids)

    project = Project.objects.get(pk=args.project_id)
    tasks = Task.objects.filter(project=project)
    if task_id_filter:
        tasks = tasks.filter(id__in=task_id_filter)
    considered = tasks.count()

    matched, unmatched, changed, created = 0, 0, 0, 0
    samples = []

    for task in tasks.select_related('project').iterator():
        image = (task.data or {}).get('image')
        results = by_image.get(image)
        if results is None:
            unmatched += 1
            continue
        matched += 1

        new_result = results
        if args.boxes_only:
            new_result = [r for r in results if r.get('type') == 'rectanglelabels']
            if keep_labels:
                new_result = [
                    r for r in new_result if set(r.get('value', {}).get('rectanglelabels') or []) & keep_labels
                ]

        if len(samples) < 3:
            samples.append((task.id, len(results), len(new_result), sorted({r.get('from_name') for r in new_result})))

        prediction = Prediction.objects.filter(task=task, model_version=args.model_version).first()
        if prediction is None:
            created += 1
            if not args.dry_run and args.yes:
                Prediction.objects.create(
                    task=task, project=project, model_version=args.model_version, score=1.0, result=new_result
                )
        elif prediction.result != new_result:
            changed += 1
            if not args.dry_run and args.yes:
                prediction.result = new_result
                prediction.score = 1.0
                prediction.save(update_fields=['result', 'score', 'updated_at'])

    print(f'Project              : {project.id} - {project.title}')
    print(f'Reference entries    : {len(by_image)}')
    print(f'Tasks considered     : {considered}')
    print(f'Matched by image     : {matched}')
    print(f'Not in reference     : {unmatched}')
    print(f'Predictions to create: {created}')
    print(f'Predictions to change: {changed}')
    print(f'Mode                 : boxes_only={args.boxes_only} keep_labels={sorted(keep_labels) or "(all)"}')
    for task_id, before, after, fields in samples:
        print(f'  sample task {task_id}: {before} results -> {after} ({fields})')

    if args.dry_run:
        print('Dry run: nothing written')
    elif not args.yes:
        print('Refusing to write without --yes')
        return 1
    else:
        print('Done')
    return 0


if __name__ == '__main__':
    sys.exit(main())
