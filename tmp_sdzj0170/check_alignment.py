# -*- coding: utf-8 -*-
"""验证 r4 扫描口径：SDZJ0170 数据层分卷 7 文件（不含 catalog/all）六字形计数"""
import re, sys
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
DL = Path(r"D:\OH-WorkSpace\Destiny_agent\tmp_sdzj0170\datalayer_md")
DATA_FILES = ["sd_sdzj0170_v1.md", "sd_sdzj0170_v2.md", "sd_sdzj0170_v3.md",
              "sd_sdzj0170_v4.md", "sd_sdzj0170_v5.md", "sd_sdzj0170_v7.md",
              "sd_sdzj0170_mingtu.md"]

def strip_code(text):
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"\[\[([^\]|]+)(\|[^\]]+)?\]\]", r"\1", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"^[#>*\-\d\.\s`|]+", "", text, flags=re.M)
    return text

dt = "".join(strip_code((DL / fn).read_text(encoding="utf-8")) for fn in DATA_FILES)
for ch in ["殺", "㐫", "隂", "郷", "賦", "隨", "祿", "衝", "剋", "尅"]:
    print(f"{ch}: {dt.count(ch)}")
