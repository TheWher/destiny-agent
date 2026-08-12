# -*- coding: utf-8 -*-
"""最终验证：p66 凶 字隔离 + 多字体基准"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
import numpy as np
from PIL import Image, ImageDraw, ImageFont

BASE = r"D:\OH-WorkSpace\Destiny_agent\tmp_sdzj0170\shuge_ocr\key_pages"


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
    print(f"{name}: h={h} cw={cw} topbar={best_run/cw:.2f}")
    return best_run / cw


def render_ref(ch, font_path, size=180):
    f = ImageFont.truetype(font_path, size)
    img = Image.new("L", (size + 30, size + 30), 255)
    d = ImageDraw.Draw(img)
    d.text((15, 8), ch, font=f, fill=0)
    a = np.array(img)
    ink = a < 150
    ys, xs = np.where(ink)
    return a, (ys.min(), ys.max() + 1, xs.min(), xs.max() + 1)


print("=== 多字体基准 ===")
for fp, fname in (
    (r"C:\Windows\Fonts\simsun.ttc", "SimSun"),
    (r"C:\Windows\Fonts\simkai.ttf", "SimKai"),
):
    for ch in ("凶", "卤", "㐫"):
        try:
            a, bb = render_ref(ch, fp)
            test_bbox(a, *bb, f"{fname}-{ch}")
        except Exception as e:
            print(fname, ch, "ERR", e)

print("=== p66 凶 字隔离 (y 5520~5880, x 1420~1740) ===")
a66 = np.array(Image.open(BASE + r"\p66_full600.png").convert("L"))
test_bbox(a66, 5520, 5880, 1420, 1740, "p66-xiong")
Image.fromarray(a66[5520:5880, 1420:1740]).save(BASE + r"\p66_xiong_iso.png")

# 也测 有 (对照，正常字)
test_bbox(a66, 5140, 5560, 1420, 1740, "p66-you(对照)")
