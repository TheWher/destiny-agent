# -*- coding: utf-8 -*-
"""注疏系/摘编层/十八飞星 六字形分布快扫（成员集扩编规则层预估用，2026-08-12）"""
from pathlib import Path

SNAP = Path(r"D:\OH-WorkSpace\Destiny_agent\knowledge_base\obsidian\素材池\网页快照")
pairs = [("㐫", "凶"), ("隂", "陰"), ("郷", "鄉"), ("殺", "杀"), ("賦", "赋"), ("隨", "随")]
layer_map = {
    "ziweicn": "注疏系",
    "ziweishuyuan": "摘编层",
    "jsdj": "摘编层",
    "ziwei-shibafeixing": "十八飞星",
    "ziwei-quanshu": "古籍层",
}
for prefix, layer in layer_map.items():
    files = sorted(SNAP.glob(f"*-{prefix}-*.md"))
    if not files:
        continue
    text = "\n".join(f.read_text(encoding="utf-8", errors="replace") for f in files)
    counts = " ".join(f"{a}:{text.count(a)}/{b}:{text.count(b)}" for a, b in pairs)
    print(f"{layer} ({len(files)} files, {len(text)} chars): {counts}")
