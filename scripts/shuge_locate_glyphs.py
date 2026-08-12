# -*- coding: utf-8 -*-
"""OCR 框坐标定位 + 原图裁剪放大：锁定指纹句字形"""
import sys, os
sys.stdout.reconfigure(encoding="utf-8")
import fitz
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

PDF = r"D:\OH-WorkSpace\Destiny_agent\新锓希夷陈先生紫微斗数全书.七卷.宋.陈抟撰.明.潘希尹补.明代南阳堂刊本.黑白版.pdf"
OUT = r"D:\OH-WorkSpace\Destiny_agent\tmp_sdzj0170\shuge_ocr\key_pages"
os.makedirs(OUT, exist_ok=True)
DPI = 250

# (页号1-based, 关键词) 列表
TARGETS = [
    (9, "十二垣"), (9, "分布"), (9, "星之分野"),
    (10, "祿逢"), (10, "沖破"), (10, "藏"), (10, "生尅"), (10, "生克"), (10, "之機"),
    (18, "聚要"), (18, "最宜"),
    (21, "相貌加刑"), (21, "刑"), (21, "難免"),
    (108, "生"), (108, "之機"),
]

ocr = RapidOCR()
doc = fitz.open(PDF)

def render(pno):
    pix = doc[pno].get_pixmap(dpi=DPI)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    return img

cache = {}
for pno1, kw in TARGETS:
    pno = pno1 - 1
    if pno not in cache:
        cache[pno] = render(pno)
    img = cache[pno]
    # OCR 该页
    p = os.path.join(OUT, f"_t{pno1}.png")
    img.save(p)
    res, _ = ocr(p)
    found = False
    for box, text, score in res:
        if kw in text:
            xs = [pt[0] for pt in box]; ys = [pt[1] for pt in box]
            x0, x1 = int(min(xs)) - 15, int(max(xs)) + 15
            y0, y1 = int(min(ys)) - 15, int(max(ys)) + 15
            x0, y0 = max(0, x0), max(0, y0)
            crop = img.crop((x0, y0, x1, y1))
            scale = 4
            crop = crop.resize((crop.width * scale, crop.height * scale), Image.LANCZOS)
            out = os.path.join(OUT, f"p{pno1}_{kw}.png")
            crop.save(out)
            print(f"[第{pno1}页] '{kw}' -> {out} (OCR: {text[:40]})")
            found = True
            break
    if not found:
        # 模糊匹配：无空格变体
        res, _ = ocr(p)
        for box, text, score in res:
            if kw in text.replace(" ", ""):
                xs = [pt[0] for pt in box]; ys = [pt[1] for pt in box]
                x0, x1 = int(min(xs)) - 15, int(max(xs)) + 15
                y0, y1 = int(min(ys)) - 15, int(max(ys)) + 15
                x0, y0 = max(0, x0), max(0, y0)
                crop = img.crop((x0, y0, x1, y1))
                crop = crop.resize((crop.width * 4, crop.height * 4), Image.LANCZOS)
                out = os.path.join(OUT, f"p{pno1}_{kw}.png")
                crop.save(out)
                print(f"[第{pno1}页] '{kw}' (fuzzy) -> {out} (OCR: {text[:40]})")
                found = True
                break
    if not found:
        print(f"[第{pno1}页] '{kw}' 未定位")
doc.close()
