# -*- coding: utf-8 -*-
import sys, re
sys.stdout.reconfigure(encoding="utf-8")

text = open("tmp_sdzj0170/shuge_ocr/fulltext_p1_528.txt", encoding="utf-8").read()

def norm(t):
    return re.sub(r"[\s，。、；：？！「」『』（）()\"'\u3000]", "", t)

n = norm(text)

feats = ["藏凶", "藏卤", "逢沖破", "逢冲破", "逢衝破", "諸凶在", "諸卤",
         "難免", "难免", "心亂", "心乱", "制化", "之機", "緊要", "聚要"]
for f in feats:
    print(f, n.count(f))

# 心亂 相关上下文
print("--- 心亂/心乱 上下文 ---")
for pat in ["心亂", "心乱"]:
    for m in list(re.finditer(pat, n))[:3]:
        s = max(0, m.start()-15); e = min(len(n), m.end()+15)
        print(pat, "...", n[s:e], "...")

# 必有卤祸 上下文（刻本擎羊条目）
print("--- 必有卤祸 ---")
for m in list(re.finditer("卤祸", n))[:3]:
    s = max(0, m.start()-25); e = min(len(n), m.end()+25)
    print("...", n[s:e], "...")
