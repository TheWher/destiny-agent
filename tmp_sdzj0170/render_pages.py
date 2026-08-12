# -*- coding: utf-8 -*-
"""渲染刻本 PDF 指定页为高分辨率 PNG，供回图视觉核对"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
import fitz

doc = fitz.open(r"D:\OH-WorkSpace\Destiny_agent\新锓希夷陈先生紫微斗数全书.七卷.宋.陈抟撰.明.潘希尹补.明代南阳堂刊本.黑白版.pdf")
print(f"页数: {doc.page_count}")
for p in (66, 418):
    page = doc[p - 1]
    pix = page.get_pixmap(dpi=300)
    out = rf"D:\OH-WorkSpace\Destiny_agent\tmp_sdzj0170\shuge_ocr\key_pages\p{p}_full300.png"
    pix.save(out)
    print(p, pix.width, pix.height, out)
