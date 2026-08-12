# -*- coding: utf-8 -*-
"""单列精确裁切：col8 必有凶禍縱 段 @600dpi，逐字测试"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
import numpy as np
from PIL import Image

BASE = r"D:\OH-WorkSpace\Destiny_agent\tmp_sdzj0170\shuge_ocr\key_pages"
a = np.array(Image.open(BASE + r"\p66_full600.png").convert("L"))

x0, x1, y0, y1 = 1420, 1740, 5250, 6050
strip = a[y0:y1, x0:x1]
ink = strip < 150
rowsum = ink.sum(axis=1)
W = x1 - x0
active = rowsum > W * 0.015
bands = []
start = None
for i, act in enumerate(active):
    if act and start is None:
        start = i
    elif not act and start is not None:
        if i - start > 12:
            bands.append((start, i))
        start = None
if start is not None:
    bands.append((start, len(active)))
print("bands:", [(b[0], b[1], b[1] - b[0]) for b in bands])

for idx, (by0, by1) in enumerate(bands):
    ch = a[y0 + by0 : y0 + by1, x0:x1]
    cink = ch < 150
    h, w = cink.shape
    colsum = cink.sum(axis=0)
    xs = np.where(colsum > 0)[0]
    xl, xr = xs.min(), xs.max()
    cw = xr - xl + 1
    best_run = 0
    for r in range(int(h * 0.05), int(h * 0.25)):
        row = cink[r, xl : xr + 1]
        run = best = 0
        for v in row:
            run = run + 1 if v else 0
            best = max(best, run)
        best_run = max(best_run, best)
    ratio = best_run / cw
    top_ink = cink[int(h * 0.05) : int(h * 0.25), xl : xr + 1].sum() / (
        (int(h * 0.25) - int(h * 0.05)) * cw
    )
    print(f"char{idx}: h={h} cw={cw} topbar_ratio={ratio:.2f} top_ink_frac={top_ink:.2f}")
    img = Image.fromarray(a[y0 + by0 : y0 + by1, x0:x1])
    img.save(BASE + rf"\p66_600_char{idx}.png")
