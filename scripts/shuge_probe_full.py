# -*- coding: utf-8 -*-
"""刻本 OCR 全文指纹探针 + 关键句上下文提取（2026-08-12 质量闸用）"""
import re, sys
sys.stdout.reconfigure(encoding="utf-8")

FULL = r"D:\OH-WorkSpace\Destiny_agent\tmp_sdzj0170\shuge_ocr\fulltext_p1_528.txt"
text = open(FULL, encoding="utf-8").read()

# 页切分
pages = re.split(r"===== 第(\d+)页 =====\n", text)
# pages = ['', '1', p1text, '2', p2text, ...]
page_map = {}
for i in range(1, len(pages), 2):
    page_map[int(pages[i])] = pages[i + 1]

print(f"总页数: {len(page_map)}\n")

PROBES = [
    ("禄逢冲破（目标：祿逢沖破，吉處藏㐫）", ["禄逢", "祿逢", "沖破", "冲破"]),
    ("生尅之機（目标：星臨廟旺再觀生尅之機）", ["生尅", "生剋", "生过", "之機", "制化之理"]),
    ("辨生尅制化", ["辨生尅", "辨生剋", "生尅制化", "生剋制化"]),
    ("相貌加刑殺，刑尅難免", ["相貌加刑", "刑殺", "刑尅", "刑剋", "刑鼓"]),
    ("其星分布一十二垣（佈/布）", ["其星分布", "十二垣", "分佈", "分布"]),
    ("夾昌夾曲 七貴/主貴", ["夾昌夾曲", "夹昌夹曲", "昌夾曲"]),
    ("諸㐫在緊要之鄉", ["諸㐫", "諸凶", "緊要", "𦂳要", "要之"]),
    ("吉處藏㐫/吉处藏凶", ["藏㐫", "藏凶", "吉處", "吉处", "藏卤"]),
    ("命身相尅/相克", ["命身相尅", "命身相剋", "命身相克"]),
    ("骨隨/骨髓 異文", ["骨隨", "骨髓", "骨随"]),
]

for name, kws in PROBES:
    print(f"===== {name} =====")
    hits = 0
    for pno in sorted(page_map):
        pt = re.sub(r"[\s\n]", "", page_map[pno])
        for kw in kws:
            idx = pt.find(kw)
            if idx >= 0:
                ctx = pt[max(0, idx - 25): idx + len(kw) + 25]
                print(f"  第{pno}页 ...{ctx}...")
                hits += 1
                break
    if hits == 0:
        print("  无命中")
    print()
