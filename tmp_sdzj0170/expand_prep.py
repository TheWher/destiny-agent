# -*- coding: utf-8 -*-
"""
成员集扩编备料：主力保真字形 数据层 vs 渲染层 对照分布（2026-08-12，不依赖书格）
字形清单（hanako 挂账 + mose 硬数据）：殺/㐫/隂/郷/賦/隨
用途：成员集扩编议题第一块决策材料——转正与否走三判定（字典层/实证层/规则层）+ 三票
口径：strip_code 与 scan_variant_report_r4.py 一致；数据层用分卷 7 文件（排除 all），渲染层用 8 快照
"""
import re, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(r"D:\OH-WorkSpace\Destiny_agent")
SNAP = ROOT / "knowledge_base/obsidian/素材池/网页快照"
DL = ROOT / "tmp_sdzj0170/datalayer_md"

PAIRS = [("殺", "杀"), ("㐫", "凶"), ("隂", "阴"), ("郷", "乡"), ("賦", "赋"), ("隨", "随")]

RENDER_FILES = sorted(SNAP.glob("2026-08-12-sdzj0170-*.md"))
DATA_FILES = ["sd_sdzj0170_v1.md", "sd_sdzj0170_v2.md", "sd_sdzj0170_v3.md",
              "sd_sdzj0170_v4.md", "sd_sdzj0170_v5.md", "sd_sdzj0170_v7.md",
              "sd_sdzj0170_mingtu.md"]


def strip_code(text):
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"\[\[([^\]|]+)(\|[^\]]+)?\]\]", r"\1", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"^[#>*\-\d\.\s`|]+", "", text, flags=re.M)
    return text


def count_in(text, ch):
    return text.count(ch)


# 渲染层聚合
rt = "".join(strip_code(f.read_text(encoding="utf-8")) for f in RENDER_FILES)
# 数据层聚合（分卷，排除 all）
dt = "".join(strip_code((DL / fn).read_text(encoding="utf-8")) for fn in DATA_FILES)

rc = len(re.sub(r"\s", "", rt))
dc = len(re.sub(r"\s", "", dt))

print("=" * 70)
print("成员集扩编备料：主力保真字形 渲染层 vs 数据层 对照（2026-08-12）")
print("=" * 70)
print(f"渲染层聚合 {len(RENDER_FILES)} 文件，内容级 {rc} 字")
print(f"数据层聚合 {len(DATA_FILES)} 文件，内容级 {dc} 字")
print("-" * 70)
print(f"{'字形':<4}{'渲染层(简)':>12}{'数据层(异)':>12}   趋势")
print("-" * 70)
for trad, simp in PAIRS:
    r_trad = count_in(rt, trad)
    r_simp = count_in(rt, simp)
    d_trad = count_in(dt, trad)
    d_simp = count_in(dt, simp)
    trend = ""
    if d_trad > 0 and r_trad == 0:
        trend = "数据层独有（渲染层已转简）"
    elif d_trad > 0 and r_trad > 0:
        trend = "两层都有（部分残留）"
    elif d_trad == 0:
        trend = "数据层无"
    print(f"{trad:>2}   渲染层 {trad}:{r_trad}/{simp}:{r_simp}   数据层 {trad}:{d_trad}/{simp}:{d_simp}   {trend}")

print("-" * 70)
print("注：趋势列是扩编三判定的实证层起点；字典层/规则层判定在议题推进时逐字头走。")
