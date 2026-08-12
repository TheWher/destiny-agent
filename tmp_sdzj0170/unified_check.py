# -*- coding: utf-8 -*-
"""统一复核：7 页 OCR 定位 + pitch 对齐单字顶封口检测（±偏移防错位）"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
import numpy as np
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

BASE = r"D:\OH-WorkSpace\Destiny_agent\tmp_sdzj0170\shuge_ocr\key_pages"
engine = RapidOCR()

# 页 → 目标短语（凶/卤 前的字数决定字在行内 index）
# 直接由 OCR 行文本内 凶/卤 的 index 决定
PAGES = (10, 18, 23, 66, 70, 201, 242)


def topbar(a, y0, y1, x0, x1, name):
    ch = a[y0:y1, x0:x1]
    cink = ch < 150
    h, w = cink.shape
    if h < 20 or w < 20:
        return None
    colsum = cink.sum(axis=0)
    xs = np.where(colsum > 0)[0]
    if len(xs) == 0:
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
    print(f"  {name}: h={h} cw={cw} topbar={ratio:.2f}")
    return ratio


for p in PAGES:
    img_path = BASE + rf"\p{p}_full300.png"
    a = np.array(Image.open(img_path).convert("L"))
    result, elapse = engine(img_path)
    print(f"\n=== p{p} ===")
    if not result:
        print("  no OCR result")
        continue
    for box, text, score in result:
        if not any(ch in text for ch in "凶卤㐫"):
            continue
        xs = [pt[0] for pt in box]
        ys = [pt[1] for pt in box]
        bx0, bx1 = int(min(xs)), int(max(xs))
        by0, by1 = int(min(ys)), int(max(ys))
        n = len(text)
        pitch = (by1 - by0) / max(n, 1)
        for idx, ch in enumerate(text):
            if ch not in "凶卤㐫":
                continue
            cy = by0 + idx * pitch
            for off in (0.0, -0.25, 0.25):
                topbar(
                    a,
                    int(cy + off * pitch),
                    int(cy + (1 + off) * pitch),
                    bx0 - 10,
                    bx1 + 10,
                    f"p{p} '{text}' [{idx}]={ch} off{off:+.2f}",
                )
