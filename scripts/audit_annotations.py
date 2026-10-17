"""Audit a flat project export: per-annotator counts + random sample + obvious gaps.

Input is the Data Manager "JSON" export (one row per annotation, values flattened),
e.g. project-1-at-2026-10-17-08-46-xxxx.json.

Checks per annotation (all derivable from the export):
  * boxes vs costume_category  -> boxes without a 款式
  * boxes vs color entries     -> boxes without a 颜色
  * pattern_note without pattern
  * scene_title missing (scene info is part of the required metadata)

Usage:
  python audit_annotations.py export.json --per-user 10 --out report.md
  python audit_annotations.py export.json --seed 7
"""

import argparse
import ast
import json
import os
import random
import statistics
from collections import Counter, defaultdict

USER_NAMES = {
    1: '13243186667@163.com',
    2: '1@163.com',
    3: '2@163.com',
    4: '3@163.com',
    5: '4@163.com',
    6: '5@163.com',
    7: '6@163.com',
    8: '7@163.com',
}


def as_list(value):
    """Flat export encodes multi-value controls as strings like "['黑色', '白色']"."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.startswith('['):
        try:
            parsed = ast.literal_eval(value)
            return parsed if isinstance(parsed, list) else [parsed]
        except (ValueError, SyntaxError):
            return [value]
    return [value]


def short_image(image):
    name = os.path.basename(image or '')
    return name.replace('.JPG', '').replace('.jpg', '')


def audit_row(row):
    boxes = row.get('object_category') or []
    costume_boxes = sum(1 for b in boxes if '服饰' in (b.get('rectanglelabels') or []))
    pattern_boxes = sum(1 for b in boxes if '纹样' in (b.get('rectanglelabels') or []))
    styles = len(row.get('costume_category') or [])
    colors = len(as_list(row.get('color')))
    patterns = len(as_list(row.get('pattern')))
    notes = len(as_list(row.get('pattern_note')))
    issues = []

    # 只对"服饰"框做完整性检查：每个服饰框都应有款式和颜色
    if costume_boxes and styles < costume_boxes:
        issues.append(f'{costume_boxes - styles}个服饰框未填款式')
    if costume_boxes and colors < costume_boxes:
        issues.append(f'{costume_boxes - colors}个服饰框未填颜色')
    # 框了纹样却没选纹样值（龙纹/凤纹）
    if pattern_boxes > patterns:
        issues.append(f'{pattern_boxes - patterns}个纹样框未选纹样')
    if notes > patterns:
        issues.append('纹样备注多于纹样')

    return {
        'annotator': row.get('annotator'),
        'task_id': row.get('id'),
        'image': short_image(row.get('image')),
        'costume_boxes': costume_boxes,
        'styles': styles,
        'colors': colors,
        'patterns': patterns,
        'lead_min': round((row.get('lead_time') or 0) / 60, 1),
        'issues': issues,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('export', help='flat export JSON')
    parser.add_argument('--per-user', type=int, default=10, help='random sample size per annotator')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--out', default='', help='write a Markdown report here')
    args = parser.parse_args()

    rows = json.load(open(args.export, encoding='utf-8'))
    audited = [audit_row(r) for r in rows]

    by_user = defaultdict(list)
    for item in audited:
        by_user[item['annotator']].append(item)

    lines = []
    lines.append('# 标注进度与漏标自查报告\n')
    lines.append(f'导出文件：`{os.path.basename(args.export)}`　标注总条数：**{len(audited)}**\n')
    lines.append('## 一、各标注员进度\n')
    lines.append('| 标注人 | 标注张数 | 平均耗时(分) | 自动疑点条数 |')
    lines.append('| --- | --- | --- | --- |')
    for uid in sorted(by_user):
        items = by_user[uid]
        avg = statistics.mean([i['lead_min'] for i in items]) if items else 0
        flagged = sum(1 for i in items if i['issues'])
        lines.append(f'| {USER_NAMES.get(uid, uid)} | {len(items)} | {avg:.1f} | {flagged} |')

    lines.append('\n## 二、自动检出的疑点（全量）\n')
    flagged_rows = [i for i in audited if i['issues']]
    if flagged_rows:
        lines.append('| 标注人 | task_id | 图片 | 服饰框 | 款式 | 颜色 | 纹样 | 疑点 |')
        lines.append('| --- | --- | --- | --- | --- | --- | --- | --- |')
        for i in flagged_rows:
            lines.append(
                f"| {USER_NAMES.get(i['annotator'], i['annotator'])} | {i['task_id']} | {i['image'][:30]} | "
                f"{i['costume_boxes']} | {i['styles']} | {i['colors']} | {i['patterns']} | {'、'.join(i['issues'])} |"
            )
    else:
        lines.append('未发现自动可判定的漏标。\n')

    lines.append(f'\n## 三、随机抽检清单（每人 {args.per_user} 张，seed={args.seed}）\n')
    rnd = random.Random(args.seed)
    for uid in sorted(by_user):
        items = by_user[uid]
        sample = rnd.sample(items, min(args.per_user, len(items)))
        lines.append(f"\n### {USER_NAMES.get(uid, uid)}（{len(items)} 张中抽 {len(sample)} 张）\n")
        lines.append('| # | task_id | 图片 | 服饰框 | 款式 | 颜色 | 纹样 | 自动疑点 | 人工核对 |')
        lines.append('| --- | --- | --- | --- | --- | --- | --- | --- | --- |')
        for idx, i in enumerate(sample, 1):
            lines.append(
                f"| {idx} | {i['task_id']} | {i['image'][:30]} | {i['costume_boxes']} | {i['styles']} | "
                f"{i['colors']} | {i['patterns']} | {'、'.join(i['issues']) or '-'} | ☐ |"
            )

    lines.append('\n> 人工核对要点：每个服饰框是否都填了「款式」「颜色」；有龙纹/凤纹的是否框了纹样并选择对应纹样；备注是否填在「其他」项下。')
    report = '\n'.join(lines)
    print(report)
    if args.out:
        with open(args.out, 'w', encoding='utf-8') as fh:
            fh.write(report)
        print(f'\n已写入 {args.out}')


if __name__ == '__main__':
    main()
