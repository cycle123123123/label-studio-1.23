"""Generate cross-validation task copies for a Label Studio project.

Route: instead of assigning one task to several annotators (which needs
multi-assign support and editor changes), duplicate the sampled tasks into
N copies, attach the existing annotation as a PRE-ANNOTATION (predictions)
and tag every copy with a `meta` group so results can be aggregated later.

Why predictions instead of annotations:
  predictions do not set `versions.result`, so LSF treats them as not-existing
  (Annotation.exists === false) -> Submit POSTs a brand new annotation owned by
  the current user, while the prediction stays untouched. Importing the very
  same content as an `annotation` would make the editor PATCH (overwrite) that
  row instead of creating an independent copy.

Usage (from the label_studio directory, PYTHONPATH pointing at label_studio):
  python ../scripts/make_cross_copies.py --project-id 1 --step 5 --copies 3
  python ../scripts/make_cross_copies.py --project-id 1 --step 5 --copies 3 --prelabel-source none
  python ../scripts/make_cross_copies.py --project-id 1 --step 5 --dry-run

Outputs (into --outdir, default ./cross_copies_out):
  cross_copies_import.json  - import this file into the SAME project
  cross_copies_manifest.csv - group/copy bookkeeping for later comparison
"""

import argparse
import csv
import json
import os
import sys
import uuid

import django

DEFAULT_SETTINGS = os.environ.get('DJANGO_SETTINGS_MODULE', 'core.settings.label_studio')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', DEFAULT_SETTINGS)


def parse_args():
    parser = argparse.ArgumentParser(description='Generate cross-validation task copies')
    parser.add_argument('--project-id', type=int, required=True, help='Source project id')
    parser.add_argument('--step', type=int, default=5, help='Take every Nth task by inner_id (default: 5)')
    parser.add_argument('--offset', type=int, default=1, help='1-based position of the first sampled task')
    parser.add_argument('--copies', type=int, default=3, help='How many copies per sampled task (default: 3)')
    parser.add_argument(
        '--prelabel-source',
        choices=['richest', 'latest', 'none'],
        default='richest',
        help='Which existing annotation becomes the pre-annotation (default: richest = most results)',
    )
    parser.add_argument('--phase', default='cross', help='Value stored in meta.phase (default: cross)')
    parser.add_argument('--outdir', default='cross_copies_out', help='Output directory')
    parser.add_argument('--dry-run', action='store_true', help='Only print statistics, write nothing')
    return parser.parse_args()


def pick_annotation(task, source):
    """Return the annotation result list used as pre-annotation (may be empty)."""
    if source == 'none':
        return []

    annotations = [a for a in task.annotations.all() if not a.was_cancelled]
    if not annotations:
        return []

    if source == 'richest':
        # NB: imported annotations may carry a stale result_count, so sort on the
        # real result length instead.
        annotations.sort(key=lambda a: (len(a.result or []), a.id), reverse=True)
    else:  # latest
        annotations.sort(key=lambda a: (a.created_at, a.id), reverse=True)

    result = annotations[0].result or []
    return result if isinstance(result, list) else []


def to_prediction_results(result):
    """Convert annotation results into prediction results (fresh ids, no origin)."""
    converted = []
    for item in result:
        if not isinstance(item, dict):
            continue
        clean = {
            key: value
            for key, value in item.items()
            if key not in ('id', 'origin', 'hidden', 'meta')
        }
        clean['id'] = uuid.uuid4().hex[:10]
        converted.append(clean)
    return converted


def main():
    args = parse_args()
    django.setup()

    from projects.models import Project
    from tasks.models import Task

    project = Project.objects.get(pk=args.project_id)
    tasks = list(Task.objects.filter(project=project).order_by('inner_id', 'id'))

    if not tasks:
        print(f'Project {project.id} has no tasks, nothing to do')
        return 1

    # Deterministic sampling: every N-th task of the inner_id ordering.
    start = max(args.offset - 1, 0)
    sampled = tasks[start :: max(args.step, 1)]

    rows = []
    import_payload = []
    empty_prelabels = 0

    for task in sampled:
        results = pick_annotation(task, args.prelabel_source)
        prediction_results = to_prediction_results(results)

        if not prediction_results:
            empty_prelabels += 1

        for copy_index in range(1, args.copies + 1):
            copy_task = {'data': task.data}
            if prediction_results:
                copy_task['predictions'] = [
                    {'model_version': 'prelabel', 'score': 1.0, 'result': prediction_results}
                ]
            copy_task['meta'] = {
                'cross_group': task.inner_id,
                'cross_origin_task_id': task.id,
                'copy_index': copy_index,
                'phase': args.phase,
                'sample_rule': f'inner_id_every_{args.step}_offset_{args.offset}',
            }
            import_payload.append(copy_task)
            rows.append(
                {
                    'cross_group': task.inner_id,
                    'origin_task_id': task.id,
                    'copy_index': copy_index,
                    'prelabel_results': len(prediction_results),
                }
            )

    print(f'Project            : {project.id} - {project.title}')
    print(f'Tasks in project   : {len(tasks)}')
    print(f'Sampled (1 of {args.step}): {len(sampled)}')
    print(f'Copies to create   : {len(import_payload)} ({args.copies} per sampled task)')
    print(f'Empty pre-annotations: {empty_prelabels} sampled tasks had no annotation content')
    if sampled:
        inner_ids = [t.inner_id for t in sampled]
        print(f'Sampled inner_id range: {inner_ids[0]} .. {inner_ids[-1]}')

    if args.dry_run:
        print('Dry run: nothing written')
        return 0

    outdir = args.outdir
    os.makedirs(outdir, exist_ok=True)
    json_path = os.path.join(outdir, 'cross_copies_import.json')
    csv_path = os.path.join(outdir, 'cross_copies_manifest.csv')

    with open(json_path, 'w', encoding='utf-8') as fh:
        json.dump(import_payload, fh, ensure_ascii=False, indent=1)

    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f'Written: {json_path}')
    print(f'Written: {csv_path}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
