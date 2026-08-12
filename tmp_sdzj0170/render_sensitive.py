# -*- coding: utf-8 -*-
"""渲染 4 个敏感页 (p23/p70/p201/p242) @300dpi，并输出页面的列结构（x 投影找列边界）"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
import fitz
import numpy as np
from PIL import Image

PDF = r"D:\OH-WorkSpace\Destiny_agent\新锓希夷陈先生紫微斗数全书.七卷.宋.陈抟撰.明.潘希尹补.明代南阳堂刊本.黑白版.pdf"
BASE = r"D:\OH-WorkSpace\Destiny_agent\tmp_sdzj0170\shuge_ocr\key_pages"

doc = fitz.open(PDF)
for p in (23, 70, 201, 242):
    page = doc[p - 1]
    pix = page.get_pixmap(dpi=300)
    out = BASE + rf"\p{p}_full300.png"
    pix.save(out)
    a = np.array(Image.open(out).convert("L"))
    ink = a < 150
    colsum = ink.sum(axis=0)
    # 找列间隙：连续低墨区
    H = a.shape[0]
    active = colsum > H * 0.005
    gaps = []
    in_gap = False
    for x in range(len(active)):
        if not active[x] and not in_gap:
            start = x
            in_gap = True
        elif active[x] and in_gap:
            if x - start > 8:
                gaps.append((start, x))
            in_gap = False
    if in_gap:
        gaps.append((start, len(active)))
    # 列 = 墨区（gap 之间的区段）
    segs = []
    prev = 0
    for gs, ge in gaps:
        if ge - prev > 40:
            segs.append((prev, ge))
        prev = ge
    if a.shape[1] - prev > 40:
        segs.append((prev, a.shape[1]))
    print(f"p{p}: img={a.shape[1]}x{a.shape[0]} cols={len(segs)}", segs)
