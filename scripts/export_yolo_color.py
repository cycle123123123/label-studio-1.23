"""Export a flat Label Studio export to a YOLO dataset with COLOUR as the class.

Pipeline per annotation:
  1. keep the N largest boxes, N = number of colour values (flat export loses the
     box<->attribute pairing, count matching is the best we can do)
  2. drop near-duplicate boxes (IoU > 0.5) - same performer labelled twice
  3. drop boxes whose costume_name is a headwear/prop (翎子 / 狐尾 / ...)
  4. class id = colour name

Images are EXIF-rotated (the library contains orientation=8 files) and resized to
--max-side so the dataset stays small.

Usage:
  python export_yolo_color.py --export xxx.json --images "D:/work/戏曲相关/sx/downloads/随机1500张" \
      --out D:/work/戏曲相关/sx/ml/data/yolo_color
"""

import argparse
import ast
import json
import os
import random
import re
from collections import Counter

from PIL import Image, ImageOps

COLOURS = ['黑色', '白色', '红色', '蓝色', '黄色', '绿色', '紫色', '粉色', '湖色', '香色', '不确定']
DROP_NAME_KEYS = ['翎子', '狐尾']


def parse_cli():
    ap = argparse.ArgumentParser()
    ap.add_argument('--export', required=True)
    ap.add_argument('--images', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--val-ratio', type=float, default=0.15)
    ap.add_argument('--seed', type=int, default=42)
    ap.add_argument('--max-side', type=int, default=1600)
    ap.add_argument('--drop-colours', default='', help='comma separated colour names to skip')
    ap.add_argument('--drop-uncertain', action='store_true', help='skip boxes whose colour is 不确定')
    return ap.parse_args()


def as_list(v):
    if v is None:
        return []
    if isinstance(v, list):
        return v
    if isinstance(v, str) and v.startswith('['):
        try:
            x = ast.literal_eval(v)
            return x if isinstance(x, list) else [x]
        except (ValueError, SyntaxError):
            return [v]
    return [v]


def texts(v):
    out = []
    for x in as_list(v):
        if isinstance(x, dict):
            if 'text' in x:
                out.append(''.join(x['text']))
        elif isinstance(x, str):
            out.append(x)
    return [s.strip() for s in out if s and s.strip()]


def area(b):
    return (b.get('width') or 0) * (b.get('height') or 0) / 100.0


def dedup(boxes, thr=0.5):
    items = sorted(boxes, key=area, reverse=True)
    out = []
    for b in items:
        x1, y1 = b['x'], b['y']
        x2, y2 = x1 + b['width'], y1 + b['height']
        dup = False
        for o in out:
            ox1, oy1 = o['x'], o['y']
            ox2, oy2 = ox1 + o['width'], oy1 + o['height']
            ix = max(0.0, min(x2, ox2) - max(x1, ox1))
            iy = max(0.0, min(y2, oy2) - max(y1, oy1))
            inter = ix * iy / 100.0
            union = area(b) + area(o) - inter
            if union > 0 and inter / union > thr:
                dup = True
                break
        if not dup:
            out.append(b)
    return out


def dedup_pairs(pairs, thr=0.5):
    out = []
    for b, c, nm in pairs:
        x1, y1 = b['x'], b['y']
        x2, y2 = x1 + b['width'], y1 + b['height']
        dup = False
        for o, _, _ in out:
            ox1, oy1 = o['x'], o['y']
            ox2, oy2 = ox1 + o['width'], oy1 + o['height']
            ix = max(0.0, min(x2, ox2) - max(x1, ox1))
            iy = max(0.0, min(y2, oy2) - max(y1, oy1))
            inter = ix * iy / 100.0
            union = area(b) + area(o) - inter
            if union > 0 and inter / union > thr:
                dup = True
                break
        if not dup:
            out.append((b, c, nm))
    return out


def norm(s):
    return re.sub(r'[^0-9A-Za-z\u4e00-\u9fff]', '', os.path.splitext(s)[0])


def main():
    args = parse_cli()
    rows = json.load(open(args.export, encoding='utf-8'))

    idx = {}
    for dp, _, fs in os.walk(args.images):
        for f in fs:
            if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                idx[norm(f)] = os.path.join(dp, f)

    for split in ('train', 'val'):
        os.makedirs(os.path.join(args.out, 'images', split), exist_ok=True)
        os.makedirs(os.path.join(args.out, 'labels', split), exist_ok=True)

    used_colours = Counter()
    stats = Counter()
    items = []

    for r in rows:
        boxes = r.get('object_category') or []
        if not boxes:
            stats['no_box'] += 1
            continue
        colours = [c for c in as_list(r.get('color')) if isinstance(c, str)]
        names = texts(r.get('costume_name'))
        if len(colours) != len(boxes):
            stats['colour_count_mismatch'] += 1
        n = min(len(boxes), len(colours))
        if n == 0:
            stats['no_colour'] += 1
            continue

        # flat export keeps colour[i] aligned with object_category[i]
        pairs = [(boxes[i], colours[i], names[i] if i < len(names) else '')
                 for i in range(min(len(boxes), len(colours)))]
        pairs.sort(key=lambda p: -area(p[0]))
        pairs = dedup_pairs(pairs)
        stats['boxes_deduped'] += n - len(pairs)

        drop_set = {x.strip() for x in args.drop_colours.split(',') if x.strip()}
        kept = []
        for b, c, nm in pairs:
            if c in drop_set:
                stats['dropped_by_colour'] += 1
                continue
            if args.drop_uncertain and c == '不确定':
                stats['dropped_uncertain'] += 1
                continue
            if any(k in nm for k in DROP_NAME_KEYS):
                stats['dropped_prop'] += 1
                continue
            kept.append((b, c))

        if not kept:
            stats['empty_after_filter'] += 1
            continue

        src = idx.get(norm(os.path.basename(r['image'])))
        if not src:
            stats['image_missing'] += 1
            continue

        items.append((r, kept, src))
        stats['items'] += 1
        stats['boxes'] += len(kept)
        for _, c in kept:
            used_colours[c] += 1

    rnd = random.Random(args.seed)
    rnd.shuffle(items)
    n_val = max(1, int(len(items) * args.val_ratio))
    splits = {'val': items[:n_val], 'train': items[n_val:]}

    used = [c for c in COLOURS if used_colours[c] > 0]
    cls_index = {c: i for i, c in enumerate(used)}

    for split, group in splits.items():
        for r, kept, src in group:
            name = os.path.basename(src)
            stem = os.path.splitext(name)[0]
            im = ImageOps.exif_transpose(Image.open(src)).convert('RGB')
            if args.max_side and max(im.size) > args.max_side:
                s = args.max_side / max(im.size)
                im = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
            im.save(os.path.join(args.out, 'images', split, name), quality=88, optimize=True)

            lines = []
            for b, c in kept:
                cx = (b['x'] + b['width'] / 2) / 100
                cy = (b['y'] + b['height'] / 2) / 100
                lines.append('%d %.6f %.6f %.6f %.6f' % (
                    cls_index[c], cx, cy, b['width'] / 100, b['height'] / 100))
            with open(os.path.join(args.out, 'labels', split, stem + '.txt'), 'w', encoding='utf-8') as fh:
                fh.write('\n'.join(lines))
        stats['%s_images' % split] = len(group)

    present = [c for c in COLOURS if used_colours[c] > 0]
    with open(os.path.join(args.out, 'dataset.yaml'), 'w', encoding='utf-8') as fh:
        fh.write('path: %s\n' % os.path.abspath(args.out))
        fh.write('train: images/train\nval: images/val\n')
        fh.write('names: {%s}\n' % ', '.join('%d: %s' % (i, c) for i, c in enumerate(used)))

    print('==== result ====')
    for k, v in sorted(stats.items()):
        print('%s: %s' % (k, v))
    print('colours:', dict(used_colours))
    print('dataset.yaml ->', os.path.join(args.out, 'dataset.yaml'))


if __name__ == '__main__':
    main()
