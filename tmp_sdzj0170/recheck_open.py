# -*- coding: utf-8 -*-
"""复核两个开口读数：p201 常人得凶旺門風、p23 两卤神。按行框 pitch 对齐裁单字。"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
import numpy as np
from PIL import Image

BASE = r"D:\OH-WorkSpace\Destiny_agent\tmp_sdzj0170\shuge_ocr\key_pages"


def topbar(a, y0, y1, x0, x1, name):
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


# p201 常人得凶旺門風: box x[286,463] y[2393,3528], 7字, pitch~162, 凶=第4字
a201 = np.array(Image.open(BASE + r"\p201_full300.png").convert("L"))
topbar(a201, 2860, 3060, 280, 470, "p201-凶复核")
Image.fromarray(a201[2860:3060, 280:470]).save(BASE + r"\p201_xiong_check.png")

# 邻字对照：旺(第5) 门(第6)
topbar(a201, 3022, 3184, 280, 470, "p201-旺(对照)")
topbar(a201, 3184, 3346, 280, 470, "p201-門(对照)")

# p23 两卤神: box x[1441,1727] y[766,3963], 19字, pitch~168, 卤=第4字
a23 = np.array(Image.open(BASE + r"\p23_full300.png").convert("L"))
topbar(a23, 1250, 1450, 1435, 1730, "p23-卤神复核")
Image.fromarray(a23[1250:1450, 1435:1730]).save(BASE + r"\p23_lushen_check.png")
# 邻字对照: 神(第5)
topbar(a23, 1418, 1586, 1435, 1730, "p23-神(对照)")
