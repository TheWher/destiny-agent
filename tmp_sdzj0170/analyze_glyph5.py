# -*- coding: utf-8 -*-
"""三处字形顶封口像素测试：p66 凶禍位 / p10 藏凶 / p18 不凶"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
import numpy as np
from PIL import Image

BASE = r"D:\OH-WorkSpace\Destiny_agent\tmp_sdzj0170\shuge_ocr\key_pages"


def load(path):
    return np.array(Image.open(path).convert("L"))


def band_chars(a, y0, y1, x0, x1, width_frac=0.015, min_h=20):
    strip = a[y0:y1, x0:x1]
    ink = strip < 150
    rowsum = ink.sum(axis=1)
    th = (x1 - x0) * width_frac
    active = rowsum > th
    bands = []
    start = None
    for i, act in enumerate(active):
        if act and start is None:
            start = i
        elif not act and start is not None:
            if i - start >= min_h:
                bands.append((start, i))
            start = None
    if start is not None:
        bands.append((start, len(active)))
    return bands


def test_bbox(a, y0, y1, x0, x1, name):
    ch = a[y0:y1, x0:x1]
    cink = ch < 150
    h, w = cink.shape
    colsum = cink.sum(axis=0)
    xs = np.where(colsum > 0)[0]
    if len(xs) == 0:
        print(name, "EMPTY")
        return
    xl, xr = xs.min(), xs.max()
    cw = xr - xl + 1
    best_run = 0
    for r in range(int(h * 0.05), int(h * 0.28)):
        row = cink[r, xl : xr + 1]
        run = best = 0
        for v in row:
            run = run + 1 if v else 0
            best = max(best, run)
        best_run = max(best_run, best)
    ratio = best_run / cw
    print(f"{name}: h={h} cw={cw} topbar_ratio={ratio:.2f}  (0.14=凶开口 / 0.62=卤封口)")
    return ratio


# --- p66: 3rd char in strip y[5000,6400] (凶 zone per vision 5-char read: 必有凶禍縱) ---
a66 = load(BASE + r"\p66_full600.png")
y0, y1 = 5000, 6400
x0, x1 = 1420, 1740
bands = band_chars(a66, y0, y1, x0, x1, min_h=40)
print("p66 bands:", [(b[0], b[1], b[1] - b[0]) for b in bands])
for idx, (by0, by1) in enumerate(bands):
    if len(bands) <= 6:
        test_bbox(a66, y0 + by0, y0 + by1, x0, x1, f"p66-char{idx}")

# --- p10_藏.png (4x): 其變則數之造化遠矣例曰祿逢沖破吉處藏凶馬遇空, 凶=19th ---
a10 = load(BASE + r"\p10_藏.png")
H10, W10 = a10.shape
bands10 = band_chars(a10, 0, H10, 0, W10, min_h=30)
print("p10 bands:", len(bands10), "H10=", H10)
if len(bands10) >= 19:
    by0, by1 = bands10[18]
    test_bbox(a10, by0, by1, 0, W10, "p10-凶(19th)")
# 也测 藏(18th) 和 馬(20th) 对照
for idx in (17, 19):
    if len(bands10) > idx:
        by0, by1 = bands10[idx]
        test_bbox(a10, by0, by1, 0, W10, f"p10-{idx+1}th")

# --- p18_聚要.png (4x): 入廟不凶..., 凶=4th ---
a18 = load(BASE + r"\p18_聚要.png")
H18, W18 = a18.shape
bands18 = band_chars(a18, 0, H18, 0, W18, min_h=30)
print("p18 bands:", len(bands18), "H18=", H18)
for idx in (2, 3, 4):
    if len(bands18) > idx:
        by0, by1 = bands18[idx]
        test_bbox(a18, by0, by1, 0, W18, f"p18-{idx+1}th(廟不凶)")
