# -*- coding: utf-8 -*-
"""用竖直规则线检测列边界，并输出各列 x 范围"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
import numpy as np
from PIL import Image

BASE = r"D:\OH-WorkSpace\Destiny_agent\tmp_sdzj0170\shuge_ocr\key_pages"

for p in (23, 70, 201, 242):
    a = np.array(Image.open(BASE + rf"\p{p}_full300.png").convert("L"))
    H, W = a.shape
    ink = a < 150
    # 每列 x 的"有墨行占比"
    coverage = ink.mean(axis=0)
    # 规则线：覆盖率 > 0.85 的 x
    rule_x = np.where(coverage > 0.85)[0]
    # 聚成规则线区间
    rules = []
    if len(rule_x):
        s = rule_x[0]
        prev = s
        for x in rule_x[1:]:
            if x - prev > 3:
                rules.append((s, prev))
                s = x
            prev = x
        rules.append((s, prev))
    # 列 = 规则线之间的区段
    cols = []
    prev_rule_end = 0
    for rs, re in rules:
        if re - prev_rule_end > 30:
            cols.append((prev_rule_end, re))
        prev_rule_end = rs
    if W - rules[-1][0] > 30:
        cols.append((rules[-1][1], W))
    print(f"p{p}: W={W} rules={rules}")
    print(f"   cols: {cols}")
