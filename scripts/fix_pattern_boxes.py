"""Convert mislabelled pattern boxes back to costume boxes, box by box.

Background: in the old single-control config 服饰 and 纹样 shared one
RectangleLabels, so clicking 纹样 while a costume box was selected turned the whole
costume region into a pattern box. After the v2 migration those boxes sit on
`pattern_box`. This script decides per box whether it is really a pattern:

  * no `pattern` (纹样分类) value for that box            -> costume
  * pattern == 其他 and the box's `pattern_note` mentions
    one of the "no pattern" keywords (无纹样/无样纹/素面) -> costume
  * anything else (团龙/团凤/飞禽纹/…)                    -> keep as pattern

Values are matched to boxes by identical coordinates (Label Studio writes the same
x/y/width/height for every per-region result of one box).

Usage (from the label_studio directory, PYTHONPATH pointing at label_studio):
  python ../scripts/fix_pattern_boxes.py --project-id 1 --inner-ids 126,131 --dry-run
  python ../scripts/fix_pattern_boxes.py --project-id 1 --inner-ids 126,131 --yes
  python ../scripts/fix_pattern_boxes.py --project-id 1 --inner-ids 516 --note-keywords 无,素面 --yes
"""

import argparse
import os
import sys

import django

DEFAULT_SETTINGS = os.environ.get('DJANGO_SETTINGS_MODULE', 'core.settings.label_studio')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', DEFAULT_SETTINGS)

DEFAULT_KEYWORDS = '无纹样,无样纹,素面'


def parse_args():
    parser = argparse.ArgumentParser(description='Turn 纹样 boxes back into 服装 boxes')
    parser.add_argument('--project-id', type=int, required=True)
    parser.add_argument('--inner-ids', required=True, help='Comma separated task inner_id list')
    parser.add_argument('--user-ids', default='', help='Only these annotator user ids (default: any)')
    parser.add_argument('--note-keywords', default=DEFAULT_KEYWORDS,
                        help='Notes containing any of these mark the box as "no pattern"')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--yes', action='store_true')
    return parser.parse_args()


def parse_ids(value):
    return [int(x) for x in str(value).replace(' ', '').split(',') if x]


def coord_key(value):
    return tuple(round(float(value.get(k, 0) or 0), 3) for k in ('x', 'y', 'width', 'height'))


def flatten(value, field):
    items = value.get(field) or []
    if isinstance(items, str):
        return items
    out = []
    for item in items:
        if isinstance(item, list):
            out.extend(item)
        else:
            out.append(str(item))
    return out


def plan_annotation(result, keywords):
    """Return (new_result, converted_boxes, kept_boxes, details)."""
    pattern_values = {}
    pattern_notes = {}
    for item in result:
        if not isinstance(item, dict):
            continue
        name = item.get('from_name')
        value = item.get('value') or {}
        if name == 'pattern':
            pattern_values[coord_key(value)] = flatten(value, 'taxonomy')
        elif name == 'pattern_note':
            texts = flatten(value, 'text')
            pattern_notes[coord_key(value)] = ''.join(texts)

    new_result = []
    converted = kept = 0
    details = []
    for item in result:
        if not (isinstance(item, dict) and item.get('type') == 'rectanglelabels'
                and item.get('from_name') == 'pattern_box'):
            new_result.append(item)
            continue

        value = item.get('value') or {}
        key = coord_key(value)
        labels = pattern_values.get(key)
        note = pattern_notes.get(key, '')

        if not labels:
            reason = 'no pattern value'
        elif labels == ['其他'] and any(kw in note for kw in keywords):
            reason = f'其他 + note "{note}"'
        else:
            reason = None

        if reason:
            item = dict(item)
            item['from_name'] = 'object_category'
            item.setdefault('value', {})['rectanglelabels'] = ['服装']
            converted += 1
            details.append(f'box->服装 ({reason})')
        else:
            kept += 1
            details.append(f'keep 纹样 ({labels} {note})'.strip())
        new_result.append(item)

    return new_result, converted, kept, details


def main():
    args = parse_args()
    django.setup()

    from projects.models import Project
    from tasks.models import Annotation, Task

    keywords = [k.strip() for k in args.note_keywords.split(',') if k.strip()]
    project = Project.objects.get(pk=args.project_id)
    inner_ids = parse_ids(args.inner_ids)
    user_ids = parse_ids(args.user_ids) if args.user_ids else None

    tasks = {t.inner_id: t for t in Task.objects.filter(project=project, inner_id__in=inner_ids)}
    missing = [i for i in inner_ids if i not in tasks]
    print(f'Project: {project.id} - {project.title}')
    print(f'Keywords: {keywords}')
    print(f'Inner ids: {len(inner_ids)} | found {len(tasks)} | missing {missing}\n')

    planned = []
    total_converted = total_kept = 0

    for inner_id in inner_ids:
        task = tasks.get(inner_id)
        if task is None:
            continue
        qs = Annotation.objects.filter(task=task)
        if user_ids:
            qs = qs.filter(completed_by_id__in=user_ids)
        for ann in qs:
            new_result, converted, kept, details = plan_annotation(ann.result or [], keywords)
            if converted:
                planned.append((ann, new_result))
            total_converted += converted
            total_kept += kept
            if details:
                print(f'  inner_id={inner_id} ann={ann.id}: ' + '; '.join(details))

    print(f'\nAnnotations to update: {len(planned)} | boxes converted: {total_converted} | boxes kept as 纹样: {total_kept}')
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
