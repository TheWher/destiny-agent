# -*- coding: utf-8 -*-
"""提取 detect_patterns 的格局清单"""
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
src = open("ziwei_calculator.py", encoding="utf-8").read()
start = src.index("def detect_patterns")
# 函数体结束：下一个顶格 def
rest = src[start + 10:]
nxt = rest.find("\ndef ")
end = start + 10 + nxt if nxt != -1 else len(src)
body = src[start:end]

names = re.findall(r"add_pat\('([^']+)'", body)
print("格局总数:", len(set(names)))
for n in sorted(set(names)):
    print(n)
