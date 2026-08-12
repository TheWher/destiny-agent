# -*- coding: utf-8 -*-
"""书格刻本 PDF 探查：页数、尺寸、渲染采样（给 mose OCR 预案参考）"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
import fitz

doc = fitz.open(r"D:\OH-WorkSpace\Destiny_agent\新锓希夷陈先生紫微斗数全书.七卷.宋.陈抟撰.明.潘希尹补.明代南阳堂刊本.黑白版.pdf")
print(f"页数: {doc.page_count}")
print(f"元数据: {doc.metadata.get('title')} / format={doc.metadata.get('format')}")
for i in [0, 1, min(5, doc.page_count - 1)]:
    page = doc[i]
    pix = page.get_pixmap(dpi=100)
    print(f"页{i}: 尺寸 {page.rect.width:.0f}x{page.rect.height:.0f}pt, 渲染 {pix.width}x{pix.height}px")
# 检查是否有内嵌文字
total_text = 0
for i in range(doc.page_count):
    total_text += len(doc[i].get_text().strip())
print(f"全书可提取文字总字符: {total_text}（0=纯扫描件）")
