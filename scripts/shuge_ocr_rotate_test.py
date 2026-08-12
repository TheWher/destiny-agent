# -*- coding: utf-8 -*-
"""竖排处理对比：原图 vs 旋转90° vs 高DPI"""
import sys, os
sys.stdout.reconfigure(encoding="utf-8")
import fitz
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

PDF = r"D:\OH-WorkSpace\Destiny_agent\新锓希夷陈先生紫微斗数全书.七卷.宋.陈抟撰.明.潘希尹补.明代南阳堂刊本.黑白版.pdf"
OUT = r"D:\OH-WorkSpace\Destiny_agent\tmp_sdzj0170\shuge_ocr_test"
os.makedirs(OUT, exist_ok=True)
ocr = RapidOCR()

def render(pno, dpi, rot=0):
    doc = fitz.open(PDF)
    pix = doc[pno].get_pixmap(dpi=dpi)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    doc.close()
    if rot:
        img = img.rotate(rot, expand=True)
    p = os.path.join(OUT, f"t{pno+1}_d{dpi}_r{rot}.png")
    img.save(p)
    return p

def run(p, label):
    res, elapse = ocr(p)
    t = elapse[0] if isinstance(elapse, (list, tuple)) and elapse else 0
    print(f"\n--- {label} ({t:.1f}s) ---")
    if not res:
        print("  无结果")
        return
    for box, text, score in res:
        if score >= 0.7:
            print(f"  {text} ({score:.2f})")

for pno, dpi, rot in [(8, 200, 0), (8, 300, 0), (8, 200, -90), (8, 200, 90)]:
    p = render(pno, dpi, rot)
    run(p, f"第{pno+1}页 dpi={dpi} rot={rot}")
