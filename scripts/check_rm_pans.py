# -*- coding: utf-8 -*-
"""零 token 本地核验：日照雷门/月朗天门构造盘引擎检出（守命口径）。
构造盘：1941-01-10 20:00 男（命卯，太阳卯+天梁）；1941-01-10 04:00 男（命亥，太阴亥）。"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from ziwei_calculator import ziwei_paipan, detect_patterns

CASES = [
    ("日照雷门", [1941, 1, 10, 20, 0, "男"]),
    ("月朗天门", [1941, 1, 10, 4, 0, "男"]),
]
for name, birth in CASES:
    plate = ziwei_paipan(*birth)
    ming = plate.get("ming_palace") or next((p for p in plate["palaces"] if p.get("is_ming")), None)
    if ming is None:
        for p in plate["palaces"]:
            if "命" in (p.get("name") or ""):
                ming = p
                break
    hits = [p for p in plate["palaces"] if p.get("geju_pats")] if "geju_pats" in plate.get("palaces", [{}])[0] else []
    # 直接扫格局字段
    geju = plate.get("geju") or plate.get("patterns") or []
    print(f"== {name} {birth} ==")
    print("命宫:", ming.get("name") if ming else "?",
          "地支:", ming.get("earthly_branch") if ming else "?")
    # 打印全部格局
    for key in ("geju", "patterns", "geju_pats"):
        v = plate.get(key)
        if v:
            print(f"plate[{key}]:", v)
    # 引擎格局检测（生产路径）
    pats = detect_patterns(plate)
    names = [p["name"] for p in pats]
    print("引擎格局:", names)
    for p in pats:
        if p["name"] in ("日照雷门", "月朗天门"):
            print("  命中:", p)
