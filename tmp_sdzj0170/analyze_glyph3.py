# -*- coding: utf-8 -*-
"""600DPI 单字裁切 + 顶部封口像素测试（干净版）"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
import numpy as np
from PIL import Image

BASE = r"D:\OH-WorkSpace\Destiny_agent\tmp_sdzj0170\shuge_ocr\key_pages"

# p66 600dpi：凶 字 ≈ orig y 2750~2950 (300dpi 坐标) → 600dpi = ×2
# x 列中心 ≈ 800 (300dpi) → 600dpi = 1600
a = np.array(Image.open(BASE + r"\p66_full600.png").convert("L"))
# 裁 600dpi: x 1300~1900, y 5300~6000（含 必/有/凶/禍 一段，再自动分字）
x0, x1, y0, y1 = 1300, 1900, 5200, 6050
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
print("600dpi bands:", [(b[0], b[1], b[1] - b[0]) for b in bands])


def test(by0, by1, name):
    ch = a[y0 + by0 : y0 + by1, x0:x1]
    cink = ch < 150
    h, w = cink.shape
    colsum = cink.sum(axis=0)
    xs = np.where(colsum > 0)[0]
    xl, xr = xs.min(), xs.max()
    cw = xr - xl + 1
    # 顶条检测：顶部 5%~25% 行，找最长水平连续段
    best_run = 0
    for r in range(int(h * 0.05), int(h * 0.25)):
        row = cink[r, xl : xr + 1]
        run = best = 0
        for v in row:
            run = run + 1 if v else 0
            best = max(best, run)
        best_run = max(best_run, best)
    ratio = best_run / cw
    # 顶部 25% 区域墨量占比
    top_ink = cink[int(h * 0.05) : int(h * 0.25), xl : xr + 1].sum() / (
        (int(h * 0.25) - int(h * 0.05)) * cw
    )
    print(f"{name}: h={h} cw={cw} topbar_ratio={ratio:.2f} top_ink_frac={top_ink:.2f}")
    # 存单字图供视觉复核
    c = Image.fromarray(ch[y0 and 0 or 0 :, :])
    # 重新裁：以字为准
    c2 = Image.fromarray(a[y0 + by0 : y0 + by1, x0:x1])
    c2.save(BASE + rf"\{name}.png")
    return ratio, top_ink


for idx, (by0, by1) in enumerate(bands):
    test(by0, by1, f"p66_600dpi_char{idx}")
