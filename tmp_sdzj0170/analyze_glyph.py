# -*- coding: utf-8 -*-
"""像素级字形结构分析：顶部封口检测（卤=囗封口顶横条，凶=凵开口无顶横条）"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
import numpy as np
from PIL import Image


def load(path):
    return np.array(Image.open(path).convert("L"))


def band_chars(a, y0, y1, x0, x1):
    strip = a[y0:y1, x0:x1]
    ink = strip < 150
    rowsum = ink.sum(axis=1)
    th = ink.shape[1] * 0.02
    active = rowsum > th
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
    return bands


def analyze_char(a, y0, y1, x0, x1, name):
    ch = a[y0:y1, x0:x1]
    ink = ch < 150
    h, w = ink.shape
    colsum = ink.sum(axis=0)
    xs = np.where(colsum > 0)[0]
    if len(xs) == 0:
        print(name, "EMPTY")
        return
    xl, xr = xs.min(), xs.max()
    cw = xr - xl + 1
    # 顶部 5%~30% 行内的最长水平连续墨迹 / 字宽
    top = range(int(h * 0.05), int(h * 0.30))
    best_run = 0
    best_row = -1
    for r in top:
        row = ink[r, xl : xr + 1]
        run = best = 0
        for v in row:
            run = run + 1 if v else 0
            best = max(best, run)
        if best > best_run:
            best_run = best
            best_row = r
    ratio = best_run / cw
    # 顶部 30% 区域内，横向连通段数（在字宽中线以上的行上）
    midrow = ink[int(h * 0.18), xl : xr + 1]
    segs = 0
    in_seg = False
    for v in midrow:
        if v and not in_seg:
            segs += 1
            in_seg = True
        elif not v:
            in_seg = False
    print(f"{name}: bbox_h={h} cw={cw} top_run_ratio={ratio:.2f} (best row {best_row}/{h}) mid_segs={segs}")
    return ratio, segs


BASE = r"D:\OH-WorkSpace\Destiny_agent\tmp_sdzj0170\shuge_ocr\key_pages"

# ---- p66：左列 生人必有凶禍縱 段（300dpi 坐标），自动分字 ----
a66 = load(BASE + r"\p66_full300.png")
H66, W66 = a66.shape
# 从之前回图：x 700~1000，y 2200~3500 覆盖 生人必有凶禍縱 + 前后
x0, x1, y0, y1 = 660, 1020, 2150, 3550
bands = band_chars(a66, y0, y1, x0, x1)
print("p66 strip bands:", [(b[0], b[1], b[1] - b[0]) for b in bands])
for idx, (by0, by1) in enumerate(bands):
    analyze_char(a66, y0 + by0, y0 + by1, x0, x1, f"p66#{idx}")
