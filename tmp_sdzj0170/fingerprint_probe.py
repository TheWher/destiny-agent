# -*- coding: utf-8 -*-
"""临时探针：刻本 OCR 全文内容级指纹验证（2026-08-12 韩湘生侧）"""
import re
import sys
sys.stdout.reconfigure(encoding="utf-8")

text = open("tmp_sdzj0170/shuge_ocr/fulltext_p1_528.txt", encoding="utf-8").read()

def normalize(t):
    return re.sub(r"[\s，。、；：？！「」『』（）()\"'‘’\u3000]", "", t)

norm = normalize(text)

# 内容级等价：尅/剋 互认 + 繁简/异体归一
equiv = {
    "剋": "尅", "冲": "衝", "祿": "禄", "廟": "庙", "鬥": "斗",
    "陰": "隂", "隨": "随", "賦": "赋", "夾": "夹", "貴": "贵",
    "冨": "富", "𦂳": "緊", "㐫": "凶", "凶": "㐫",
}

def equiv_norm(t):
    for a, b in equiv.items():
        t = t.replace(a, b)
    return t

cnorm = equiv_norm(norm)

pairs = [
    ("祿逢沖破，吉處藏凶", "太微賦 L29"),
    ("星臨廟旺，再觀生剋之機", "太微賦 L29"),
    ("諸凶在緊要之鄉最宜制克", "斗數準繩 L35"),
    ("辨生剋制化以定窮通", "斗數準繩 L35"),
    ("命身相克，則心亂而不閑", "斗數發微論 L37"),
    ("相貌加刑殺，刑剋難免", "斗數發微論 L37"),
]
print("== 古籍层组：原始 vs 内容级 ==")
for fp, tag in pairs:
    fp_n = normalize(fp)
    raw = fp_n in norm
    content = equiv_norm(fp_n) in cnorm
    print(("[OK]" if raw else "[MISS]") + f" {tag} | 原文: {fp}")
    print(("     内容级: [OK]" if content else "     内容级: [MISS]"))

simp = [
    ("禄逢冲破，吉处藏凶", "quanlan L1101"),
    ("夹昌夹曲主贵兮", "quanlan L163"),
    ("生克制化之机", "quanlan L335"),
]
print("== 简体组 ==")
for fp, tag in simp:
    fp_n = normalize(fp)
    print(("[OK]" if fp_n in norm else "[MISS]") + f" {tag} | {fp}")

print("== 关键字形在全文中的出现次数 ==")
for ch in ["尅", "剋", "凶", "㐫", "緊", "𦂳", "最冝", "制克", "于", "布", "佈"]:
    print(repr(ch), norm.count(ch))
