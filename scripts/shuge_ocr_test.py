# -*- coding: utf-8 -*-
"""书格刻本 OCR 测试：抽页 + 竖排处理对比"""
import sys, os
sys.stdout.reconfigure(encoding="utf-8")
import fitz
from rapidocr_onnxruntime import RapidOCR

PDF = r"D:\OH-WorkSpace\Destiny_agent\新锓希夷陈先生紫微斗数全书.七卷.宋.陈抟撰.明.潘希尹补.明代南阳堂刊本.黑白版.pdf"
OUT = r"D:\OH-WorkSpace\Destiny_agent\tmp_sdzj0170\shuge_ocr_test"
os.makedirs(OUT, exist_ok=True)

ocr = RapidOCR()

def page_to_png(pdf, pno, dpi=200, rot=0):
    doc = fitz.open(pdf)
    page = doc[pno]
    pix = page.get_pixmap(dpi=dpi)
    img = pix.tobytes("png")
    doc.close()
    p = os.path.join(OUT, f"p{pno+1}_r{rot}.png")
    with open(p, "wb") as f:
        f.write(img)
    if rot:
        from PIL import Image
        im = Image.open(p)
        im = im.rotate(rot, expand=True)
        im.save(p)
    return p

for pno in [0, 8, 20]:
    p = page_to_png(PDF, pno)
    res, elapse = ocr(p)
    t = elapse[0] if isinstance(elapse, (list, tuple)) and elapse else 0
    print(f"\n=== 第{pno+1}页 原图直识别（{t:.1f}s）===")
    if res:
        for box, text, score in res:
            print(f"  {text} ({score:.2f})")
    else:
        print("  无识别结果")
