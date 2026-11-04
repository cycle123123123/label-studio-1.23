"""Render annotation boxes onto the original stills so a human (or a vision model)
can spot missing 服饰 boxes. Companion to audit_annotations.py."""
import json, os, re, sys
from PIL import Image, ImageDraw, ImageFont

def norm(s):
    s = os.path.splitext(s)[0]
    return re.sub(r'[^0-9A-Za-z\u4e00-\u9fff]', '', s)

COLORS = {'服饰': (255, 40, 40), '纹样': (30, 110, 255), '道具': (0, 170, 80), '角色': (200, 140, 0), '脸谱': (170, 0, 170)}

def main(export_path, image_root, outdir, max_boxes=1):
    ann = json.load(open(export_path, encoding='utf-8'))
    idx = {}
    for dirpath, _, files in os.walk(image_root):
        for f in files:
            if f.lower().endswith(('.jpg', '.jpeg')):
                idx[norm(f)] = os.path.join(dirpath, f)
    os.makedirs(outdir, exist_ok=True)
    made = 0
    for r in ann:
        boxes = r.get('object_category') or []
        costume = [b for b in boxes if '服饰' in (b.get('rectanglelabels') or [])]
        if len(costume) > max_boxes:
            continue
        path = idx.get(norm(os.path.basename(r['image'])))
        if not path:
            continue
        im = Image.open(path).convert('RGB')
        W, H = im.size
        if W > 1500:
            im = im.resize((1500, int(H * 1500 / W)), Image.LANCZOS)
            W, H = im.size
        d = ImageDraw.Draw(im)
        try:
            font = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 26)
        except Exception:
            font = ImageFont.load_default()
        for b in boxes:
            lab = (b.get('rectanglelabels') or ['?'])[0]
            x, y = b['x'] / 100 * W, b['y'] / 100 * H
            w, h = b['width'] / 100 * W, b['height'] / 100 * H
            c = COLORS.get(lab, (120, 120, 120))
            d.rectangle([x, y, x + w, y + h], outline=c, width=6)
            d.text((x + 8, max(y + 4, 2)), lab, fill=c, font=font)
        # 纹样框（独立 pattern_box 字段，蓝色 + taxonomy 叶子标签）
        for b in (r.get('pattern_box') or []):
            x, y = b['x'] / 100 * W, b['y'] / 100 * H
            w, h = b['width'] / 100 * W, b['height'] / 100 * H
            c = COLORS['纹样']
            # 取最深一层叶子字符串（taxonomy 可能深层嵌套或为 None）
            node = b.get('taxonomy')
            while isinstance(node, list) and node:
                node = node[-1]
            leaf = node if isinstance(node, str) and node else ''
            d.rectangle([x, y, x + w, y + h], outline=c, width=5)
            d.text((x + 8, max(y + 4, 2)), f'纹样:{leaf}' if leaf else '纹样', fill=c, font=font)
        im.save(os.path.join(outdir, f"{r['id']}_cb{len(costume)}.jpg"), quality=82)
        made += 1
    print(f'rendered {made} images -> {outdir}')

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 1)
