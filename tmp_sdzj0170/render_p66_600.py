# -*- coding: utf-8 -*-
"""渲染 p66 @600DPI 与 p23 @300DPI，供像素级字形对比"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
import fitz

doc = fitz.open(r"D:\OH-WorkSpace\Destiny_agent\新锓希夷陈先生紫微斗数全书.七卷.宋.陈抟撰.明.潘希尹补.明代南阳堂刊本.黑白版.pdf")

for p, dpi in ((66, 600), (23, 300)):
    page = doc[p - 1]
    pix = page.get_pixmap(dpi=dpi)
    out = rf"D:\OH-WorkSpace\Destiny_agent\tmp_sdzj0170\shuge_ocr\key_pages\p{p}_full{dpi}.png"
    pix.save(out)
    print(p, pix.width, pix.height, out)
