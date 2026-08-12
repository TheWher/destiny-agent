# -*- coding: utf-8 -*-
"""字形顶封口检测：现代基准(凶/卤/㐫) + 刻本实测(p66 必有X禍, p10 藏凶, p18 不凶)"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
import numpy as np
from PIL import Image, ImageDraw, ImageFont

BASE = r"D:\OH-WorkSpace\Destiny_agent\tmp_sdzj0170\shuge_ocr\key_pages"


def load(path):
    return np.array(Image.open(path).convert("L"))


def analyze_bbox(a, y0, y1, x0, x1, name):
    ch = a[y0:y1, x0:x1]
    ink = ch < 150
    h, w = ch.shape
    colsum = ink.sum(axis=0)
    xs = np.where(colsum > 0)[0]
    if len(xs) == 0:
        print(name, "EMPTY")
        return None
    xl, xr = xs.min(), xs.max()
    cw = xr - xl + 1
    top = range(int(h * 0.05), int(h * 0.30))
    best_run = 0
    for r in top:
        row = ink[r, xl : xr + 1]
        run = best = 0
        for v in row:
            run = run + 1 if v else 0
            best = max(best, run)
        best_run = max(best_run, best)
    ratio = best_run / cw
    midrow = ink[int(h * 0.18), xl : xr + 1]
    segs = 0
    in_seg = False
    for v in midrow:
        if v and not in_seg:
            segs += 1
            in_seg = True
        elif not v:
            in_seg = False
    print(f"{name}: h={h} cw={cw} top_run_ratio={ratio:.2f} mid_segs={segs}")
    return ratio, segs


def render_ref(ch, size=180):
    f = ImageFont.truetype(r"C:\Windows\Fonts\simsun.ttc", size)
    img = Image.new("L", (size + 30, size + 30), 255)
    d = ImageDraw.Draw(img)
    d.text((15, 8), ch, font=f, fill=0)
    a = np.array(img)
    ink = a < 150
    ys, xs = np.where(ink)
    return a, (ys.min(), ys.max() + 1, xs.min(), xs.max() + 1)


print("=== 现代基准 ===")
for ch in ("凶", "卤", "㐫"):
    a, bb = render_ref(ch)
    analyze_bbox(a, *bb, f"ref-{ch}")

print("=== p10_藏.png (藏凶, 4x 回图存档) ===")
a10 = load(BASE + r"\p10_藏.png")
H, W = a10.shape
ink = a10 < 150
rowsum = ink.sum(axis=1)
active = rowsum > W * 0.02
bands = []
start = None
for i, act in enumerate(active):
    if act and start is None:
        start = i
    elif not act and start is not None:
        if i - start > 8:
            bands.append((start, i))
        start = None
if start is not None:
    bands.append((start, len(active)))
print("bands:", [(b[0], b[1], b[1] - b[0]) for b in bands])
# 找包含 凶 的位置：末尾第 2 个字（藏凶馬遇空 → 凶 是倒数第 2）
if bands:
    analyze_bbox(a10, *bands[-2], 0, W, "p10-凶?")

print("=== p18_聚要.png (入廟不凶, 4x 回图存档) ===")
a18 = load(BASE + r"\p18_聚要.png")
H, W = a18.shape
ink = a18 < 150
rowsum = ink.sum(axis=1)
active = rowsum > W * 0.02
bands = []
start = None
for i, act in enumerate(active):
    if act and start is None:
        start = i
    elif not act and start is not None:
        if i - start > 8:
            bands.append((start, i))
        start = None
if start is not None:
    bands.append((start, len(active)))
print("bands:", [(b[0], b[1], b[1] - b[0]) for b in bands])
# 入廟不凶 → 凶 是第 4 个字
if len(bands) >= 4:
    analyze_bbox(a18, *bands[3], 0, W, "p18-凶?")

print("=== p66 必有X禍 (300dpi 原图, x 700~920) ===")
a66 = load(BASE + r"\p66_full300.png")
H, W = a66.shape
x0, x1, y0, y1 = 700, 920, 1980, 3350
strip = a66[y0:y1, x0:x1]
ink = strip < 150
rowsum = ink.sum(axis=1)
active = rowsum > (x1 - x0) * 0.02
bands = []
start = None
for i, act in enumerate(active):
    if act and start is None:
        start = i
    elif not act and start is not None:
        if i - start > 8:
            bands.append((start, i))
        start = None
if start is not None:
    bands.append((start, len(active)))
print("bands:", [(b[0], b[1], b[1] - b[0]) for b in bands])
for idx, (by0, by1) in enumerate(bands):
    analyze_bbox(a66, y0 + by0, y0 + by1, x0, x1, f"p66#{idx}")
