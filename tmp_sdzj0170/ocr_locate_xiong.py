# -*- coding: utf-8 -*-
"""用 RapidOCR 定位 4 个敏感页中 凶/卤 字的检测框，再对目标字做顶封口检测"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
import numpy as np
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

BASE = r"D:\OH-WorkSpace\Destiny_agent\tmp_sdzj0170\shuge_ocr\key_pages"
engine = RapidOCR()


def topbar(a, y0, y1, x0, x1, name):
    ch = a[y0:y1, x0:x1]
    cink = ch < 150
    h, w = cink.shape
    if h < 15 or w < 15:
        print(f"{name}: too small {h}x{w}")
        return None
    colsum = cink.sum(axis=0)
    xs = np.where(colsum > 0)[0]
    if len(xs) == 0:
        print(name, "EMPTY")
        return None
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
    print(f"{name}: h={h} cw={cw} topbar={ratio:.2f}  (凶≈0.14 开口 / 卤≈0.62 封口)")
    return ratio


for p in (23, 70, 201, 242):
    img_path = BASE + rf"\p{p}_full300.png"
    a = np.array(Image.open(img_path).convert("L"))
    H, W = a.shape
    result, elapse = engine(img_path)
    print(f"\n=== p{p} OCR lines: {len(result) if result else 0} ===")
    if not result:
        continue
    for box, text, score in result:
        xs = [pt[0] for pt in box]
        ys = [pt[1] for pt in box]
        x0, x1, y0, y1 = int(min(xs)), int(max(xs)), int(min(ys)), int(max(ys))
        if ("凶" in text) or ("卤" in text) or ("㐫" in text):
            print(f"  HIT: '{text}' box x[{x0},{x1}] y[{y0},{y1}] score={score:.2f}")
            # 字级处理：在该行框内按行投影分字（竖排列 → 每字一行带）
            strip = a[y0:y1, x0:x1]
            ink = strip < 150
            rowsum = ink.sum(axis=1)
            th = (x1 - x0) * 0.02
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
            # 找到 text 中 凶/卤 是第几个字
            idxs = [i for i, ch in enumerate(text) if ch in "凶卤㐫"]
            print(f"    line_len={len(text)} 凶/卤 index={idxs} bands={len(bands)}")
            for idx in idxs:
                for offset in (-1, 0, 1):
                    bi = idx + offset
                    if 0 <= bi < len(bands):
                        by0, by1 = bands[bi]
                        topbar(a, y0 + by0, y0 + by1, x0, x1, f"p{p}-{text} idx{idx}+{offset}")
