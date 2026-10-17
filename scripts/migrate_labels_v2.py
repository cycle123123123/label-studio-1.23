"""Migrate a project's annotation / draft / prediction results from the old
single-RectangleLabels layout to the new multi-control layout.

Old (single control `object_category`, 5 labels):
    角色 / 服饰 / 道具 / 脸谱 / 纹样
New (one control per object kind):
    object_category -> 服装
    pattern_box     -> 纹样
    obj_prop        -> 道具
    obj_makeup      -> 化装   (old 脸谱, and optionally old 角色)
    (old 角色 has no counterpart -> dropped or merged into 化装, see --role)

Only `rectanglelabels` results are touched; per-region attribute results
(costume_category / color / pattern / ...) keep their from_name and follow the
box automatically, so they need no migration.

Usage (from the label_studio directory, PYTHONPATH pointing at label_studio):
  python ../scripts/migrate_labels_v2.py --project-id 1 --dry-run
  python ../scripts/migrate_labels_v2.py --project-id 1 --role makeup --yes
"""

import argparse
import copy
import os
import sys
from collections import Counter

import django

DEFAULT_SETTINGS = os.environ.get('DJANGO_SETTINGS_MODULE', 'core.settings.label_studio')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', DEFAULT_SETTINGS)

# old label -> (new from_name, new label)
LABEL_MAP = {
    '服饰': ('object_category', '服装'),
    '纹样': ('pattern_box', '纹样'),
    '道具': ('obj_prop', '道具'),
    '脸谱': ('obj_makeup', '化装'),
}
ROLE_LABEL = '角色'


def parse_args():
    parser = argparse.ArgumentParser(description='Migrate labels to the v2 multi-control layout')
    parser.add_argument('--project-id', type=int, required=True)
    parser.add_argument('--role', choices=['drop', 'makeup'], default='drop',
                        help='What to do with the old 角色 label (no counterpart in v2)')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--yes', action='store_true', help='Confirm writing')
    parser.add_argument('--skip-predictions', action='store_true', help='Do not touch prediction rows')
    parser.add_argument('--skip-drafts', action='store_true', help='Do not touch draft rows')
    return parser.parse_args()


def migrate_results(result, role_mode, stats):
    """Return (new_result, changed). Works on a deep copy so `changed` is reliable."""
    original = copy.deepcopy(result or [])
    out = []
    for item in copy.deepcopy(original):
        if not isinstance(item, dict) or item.get('type') != 'rectanglelabels':
            out.append(item)
            continue

        labels = (item.get('value') or {}).get('rectanglelabels') or []
        if not labels:
            out.append(item)
            continue

        new_labels = []
        dropped = False
        for label in labels:
            if label in LABEL_MAP:
                from_name, new_label = LABEL_MAP[label]
                item['from_name'] = from_name
                new_labels.append(new_label)
                stats[(label, from_name, new_label)] += 1
            elif label == ROLE_LABEL:
                if role_mode == 'drop':
                    dropped = True
                    stats[(label, 'DROPPED', '')] += 1
                else:
                    item['from_name'] = 'obj_makeup'
                    new_labels.append('化装')
                    stats[(label, 'obj_makeup', '化装')] += 1
            else:
                new_labels.append(label)

        if dropped:
            continue
        if new_labels != labels:
            item.setdefault('value', {})['rectanglelabels'] = new_labels
        out.append(item)

    return out, out != original


def main():
    args = parse_args()
    django.setup()

    from django.db import transaction
    from projects.models import Project
    from tasks.models import Annotation, AnnotationDraft, Prediction

    project = Project.objects.get(pk=args.project_id)
    stats = Counter()
    touched = Counter()
    failed = 0

    jobs = []
    jobs.append(('annotation', Annotation.objects.filter(project=project)))
    if not args.skip_drafts:
        jobs.append(('draft', AnnotationDraft.objects.filter(task__project=project)))
    if not args.skip_predictions:
        jobs.append(('prediction', Prediction.objects.filter(project=project)))

    print(f'Project: {project.id} - {project.title}')
    print(f'Role handling: {args.role}\n')

    planned = []
    for kind, queryset in jobs:
        for row in queryset.iterator():
            try:
                new_result, changed = migrate_results(row.result, args.role, stats)
            except Exception as exc:  # malformed draft/result: leave untouched
                failed += 1
                print(f'  ! {kind} id={row.id} skipped: {exc}')
                continue
            if changed:
                touched[kind] += 1
                planned.append((row, new_result))

    print('Mapping statistics (label occurrences):')
    for (old, new_from, new_label), count in sorted(stats.items(), key=lambda x: -x[1]):
        target = 'DROPPED' if new_from == 'DROPPED' else f'{new_from} / {new_label}'
        print(f'  {old:4s} -> {target:28s} {count}')
    print()
    print(f'Rows to update: annotations={touched["annotation"]}, drafts={touched["draft"]}, predictions={touched["prediction"]}'
          f' | skipped/errors={failed}')

    if args.dry_run:
        print('Dry run: nothing written')
        return 0
    if not args.yes:
        print('Refusing to write without --yes')
        return 1

    with transaction.atomic():
        for row, new_result in planned:
            row.result = new_result
            row.save(update_fields=['result'])

    # label counters in the project summary are now stale
    if hasattr(project, 'summary'):
        project.summary.reset(tasks_data_based=False)

    print(f'Done: updated {len(planned)} rows')
    return 0


if __name__ == '__main__':
    sys.exit(main())
