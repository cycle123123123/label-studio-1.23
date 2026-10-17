"""Convert mislabelled pattern boxes back to costume boxes.

Background: in the old single-control config the "服饰" and "纹样" labels lived in
the same RectangleLabels, so selecting a costume box and clicking 纹样 turned the
whole costume region into a pattern box. After the v2 migration those boxes now sit
on `pattern_box` (label 纹样). This script moves them back to
`object_category` / 服装, but ONLY for annotations that carry no real pattern value
(no `pattern` result) - i.e. the boxes are clearly not pattern annotations.

Usage (from the label_studio directory, PYTHONPATH pointing at label_studio):
  python ../scripts/fix_pattern_boxes.py --project-id 1 --inner-ids 126,131,156 --dry-run
  python ../scripts/fix_pattern_boxes.py --project-id 1 --inner-ids 126,131,156 --yes
  python ../scripts/fix_pattern_boxes.py --project-id 1 --inner-ids 126,131,156 --only-missing-pattern --yes
"""

import argparse
import os
import sys

import django

DEFAULT_SETTINGS = os.environ.get('DJANGO_SETTINGS_MODULE', 'core.settings.label_studio')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', DEFAULT_SETTINGS)


def parse_args():
    parser = argparse.ArgumentParser(description='Turn 纹样 boxes back into 服装 boxes')
    parser.add_argument('--project-id', type=int, required=True)
    parser.add_argument('--inner-ids', required=True, help='Comma separated task inner_id list')
    parser.add_argument('--user-ids', default='', help='Only these annotator user ids (default: any)')
    parser.add_argument('--only-missing-pattern', action='store_true', default=True,
                        help='Only convert when the annotation has no pattern value (default on)')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--yes', action='store_true')
    return parser.parse_args()


def parse_ids(value):
    return [int(x) for x in str(value).replace(' ', '').split(',') if x]


def main():
    args = parse_args()
    django.setup()

    from projects.models import Project
    from tasks.models import Annotation, Task

    project = Project.objects.get(pk=args.project_id)
    inner_ids = parse_ids(args.inner_ids)
    user_ids = parse_ids(args.user_ids) if args.user_ids else None

    tasks = {t.inner_id: t for t in Task.objects.filter(project=project, inner_id__in=inner_ids)}
    missing = [i for i in inner_ids if i not in tasks]
    print(f'Project: {project.id} - {project.title}')
    print(f'Inner ids requested: {len(inner_ids)} | found: {len(tasks)} | missing: {missing}\n')

    planned = []
    skipped_pattern = 0
    skipped_no_box = 0

    for inner_id in inner_ids:
        task = tasks.get(inner_id)
        if task is None:
            continue
        qs = Annotation.objects.filter(task=task)
        if user_ids:
            qs = qs.filter(completed_by_id__in=user_ids)
        for ann in qs:
            result = ann.result or []
            has_pattern = any(r.get('from_name') == 'pattern' for r in result if isinstance(r, dict))
            boxes = [
                r for r in result
                if isinstance(r, dict) and r.get('type') == 'rectanglelabels' and r.get('from_name') == 'pattern_box'
            ]
            if not boxes:
                skipped_no_box += 1
                continue
            if has_pattern and args.only_missing_pattern:
                skipped_pattern += 1
                print(f'  inner_id={inner_id} ann={ann.id}: has pattern value -> keep ({len(boxes)} boxes)')
                continue
            new_result = []
            for r in result:
                if isinstance(r, dict) and r.get('type') == 'rectanglelabels' and r.get('from_name') == 'pattern_box':
                    r = dict(r)
                    r['from_name'] = 'object_category'
                    r.setdefault('value', {})['rectanglelabels'] = ['服装']
                new_result.append(r)
            planned.append((ann, new_result))
            print(f'  inner_id={inner_id} ann={ann.id} user={ann.completed_by_id}: {len(boxes)} box(es) 纹样 -> 服装')

    print(f'\nPlanned updates: annotations={len(planned)} | skipped(has pattern)={skipped_pattern} | no box={skipped_no_box}')
    if args.dry_run:
        print('Dry run: nothing written')
        return 0
    if not args.yes:
        print('Refusing to write without --yes')
        return 1

    updated = 0
    for ann, new_result in planned:
        updated += Annotation.objects.filter(pk=ann.pk).update(result=new_result)
    if hasattr(project, 'summary'):
        project.summary.reset(tasks_data_based=False)
    print(f'Done: updated {updated} annotations')
    return 0


if __name__ == '__main__':
    sys.exit(main())
