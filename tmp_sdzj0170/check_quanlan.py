# -*- coding: utf-8 -*-
"""核 quanlan 剋/尅/克 实际计数"""
import re, sys
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
raw = Path(r"D:\OH-WorkSpace\Destiny_agent\knowledge_base\obsidian\素材池\网页快照\2026-08-11-ziwei-quanshu-quanlan.md").read_text(encoding="utf-8")
text = re.sub(r"```.*?```", "", raw, flags=re.S)
text = re.sub(r"\[\[([^\]|]+)(\|[^\]]+)?\]\]", r"\1", text)
text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
text = re.sub(r"^[#>*\-\d\.\s`|]+", "", text, flags=re.M)
for ch in ["剋", "尅", "克"]:
    print(f"{ch}: {text.count(ch)}")
print("剋+尅:", text.count("剋") + text.count("尅"))
