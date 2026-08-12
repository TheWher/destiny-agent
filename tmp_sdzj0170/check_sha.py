# -*- coding: utf-8 -*-
"""核对摘编层 殺 分布（mose 说 jsdj 8 处，扫描显示摘编层 殺 11 处）"""
import re, sys
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
SNAP = Path(r"D:\OH-WorkSpace\Destiny_agent\knowledge_base\obsidian\素材池\网页快照")

def strip_code(text):
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"\[\[([^\]|]+)(\|[^\]]+)?\]\]", r"\1", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"^[#>*\-\d\.\s`|]+", "", text, flags=re.M)
    return text

total = 0
for f in sorted(SNAP.glob("*.md")):
    name = f.name
    if not ("ziweishuyuan" in name or "jsdj" in name):
        continue
    text = strip_code(f.read_text(encoding="utf-8"))
    n = text.count("殺")
    if n:
        total += n
        print(f"{name}: 殺 {n}")
print(f"摘编层 殺 合计: {total}")
