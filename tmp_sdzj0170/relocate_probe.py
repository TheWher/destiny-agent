# -*- coding: utf-8 -*-
import sys, re
sys.stdout.reconfigure(encoding="utf-8")

text = open("tmp_sdzj0170/shuge_ocr/fulltext_p1_528.txt", encoding="utf-8").read()
lines = text.split("\n")

# 找所有「卤祸」出现的行号和页号
page = 0
for i, ln in enumerate(lines, 1):
    m = re.search(r"第(\d+)页", ln)
    if m:
        page = int(m.group(1))
    if "卤祸" in ln:
        print(f"行 {i} → 第{page}页")
        s = max(0, ln.find("卤祸")-40); e = min(len(ln), ln.find("卤祸")+25)
        print(f"  ...{ln[s:e]}...")

# 找擎羊条目「六甲六戊」的位置
print("\n=== 六甲六戊 ===")
page = 0
for i, ln in enumerate(lines, 1):
    m = re.search(r"第(\d+)页", ln)
    if m:
        page = int(m.group(1))
    if "六甲六戊" in ln:
        print(f"行 {i} → 第{page}页")
        s = max(0, ln.find("六甲六戊")-35); e = min(len(ln), ln.find("六甲六戊")+20)
        print(f"  ...{ln[s:e]}...")

# 找 66 页完整内容看看有没有擎羊段
print("\n=== 第66页全文 ===")
page = 0
buf = []
for ln in lines:
    m = re.search(r"第(\d+)页", ln)
    if m:
        if buf and page == 66:
            break
        page = int(m.group(1))
        buf = []
    else:
        buf.append(ln)
print("".join(buf)[:800])
