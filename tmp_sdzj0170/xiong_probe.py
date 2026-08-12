# -*- coding: utf-8 -*-
import sys, re
sys.stdout.reconfigure(encoding="utf-8")

text = open("tmp_sdzj0170/shuge_ocr/fulltext_p1_528.txt", encoding="utf-8").read()
lines = text.split("\n")

# 找 OCR 里 4 处「凶」的位置（分歧点：若为开口形=真混标准凶；封口形=OCR 双向混淆）
page = 0
for i, ln in enumerate(lines, 1):
    m = re.search(r"第(\d+)页", ln)
    if m:
        page = int(m.group(1))
    for mm in re.finditer("凶", ln):
        s = max(0, mm.start()-20); e = min(len(ln), mm.end()+15)
        print(f"行 {i} → 第{page}页 | ...{ln[s:e]}...")

# 卤 235 处的页分布（抽样看是否集中于某几页）
print("\n=== 卤 出现页分布（前 25 页）===")
from collections import Counter
pages = []
page = 0
for ln in lines:
    m = re.search(r"第(\d+)页", ln)
    if m:
        page = int(m.group(1))
    pages += [page] * ln.count("卤")
for p, c in Counter(pages).most_common(25):
    print(f"  第{p}页: {c} 处")
