# -*- coding: utf-8 -*-
import sys, re
sys.stdout.reconfigure(encoding="utf-8")

text = open("tmp_sdzj0170/shuge_ocr/fulltext_p1_528.txt", encoding="utf-8").read()
lines = text.split("\n")

def page_of_line(lineno):
    """按分页标记统计行号→页号（1-indexed 行号）。"""
    page = 0
    for i, ln in enumerate(lines, 1):
        m = re.search(r"第(\d+)页", ln)
        if m:
            page = int(m.group(1))
        if i == lineno:
            return page, ln.strip()
    return None, None

for ln in [39, 72, 207, 1531]:
    p, content = page_of_line(ln)
    print(f"行 {ln} → 第{p}页 | {content[:40]}")

# 刻本 207 行上下文
print("\n=== 刻本 207 行附近 ===")
for i in range(205, 210):
    print(f"  {i}: {lines[i-1].strip()[:60]}")

# 数据层 v1 同句上下文
v1 = open("tmp_sdzj0170/datalayer_md/sd_sdzj0170_v1.md", encoding="utf-8").read()
print("\n=== 数据层 v1「必有卤禍」上下文 ===")
for m in re.finditer("卤", v1):
    s = max(0, m.start()-40); e = min(len(v1), m.end()+40)
    print("  ...", v1[s:e].replace("\n", "|"), "...")

# 刻本 418 页「二卤祸」上下文
print("\n=== 刻本 418 页附近 ===")
for i in range(1528, 1534):
    print(f"  {i}: {lines[i-1].strip()[:60]}")
