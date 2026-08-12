# -*- coding: utf-8 -*-
"""r4 快速核对：数据层 datalayer_md 真异体计数（不入库，只核数）"""
import re, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")

dl = Path(r"D:\OH-WorkSpace\Destiny_agent\tmp_sdzj0170\datalayer_md")
TRUE = {"衝", "沖", "剋", "佈"}

def strip_code(t):
    t = re.sub(r"```.*?```", "", t, flags=re.S)
    t = re.sub(r"\[\[([^\]|]+)(\|[^\]]+)?\]\]", r"\1", t)
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"^[#>*\-\d\.\s`|]+", "", t, flags=re.M)
    return t

tot_chars = 0; tot_true = 0; tot_ke = 0; detail = []
for f in sorted(dl.glob("*.md")):
    raw = f.read_text(encoding="utf-8")
    text = strip_code(raw)
    chars = len(re.sub(r"\s", "", text))
    tc = {ch: text.count(ch) for ch in TRUE if text.count(ch)}
    ke = text.count("尅")
    kt = sum(tc.values())
    tot_chars += chars; tot_true += kt; tot_ke += ke
    detail.append((f.name, chars, kt, tc, ke))
for name, chars, kt, tc, ke in detail:
    print(f"{name}: 内容级{chars} 真异体{kt} {tc} 尅{ke}")
print(f"TOTAL: 内容级{tot_chars} 真异体{tot_true} 尅{tot_ke}")
print(f"数据层真异体密度: {tot_true/tot_chars*10000:.2f}/万字")
