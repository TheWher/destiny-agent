#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""min_score 阈值评估：扫阈值，测正样本误杀率 + 负样本过滤率，找分界区间。

方法（monkeypatch 模块常量，不碰生产代码）：
- 正样本：seed_pairs.json 87 run 对，exact_contain 命中判定（复用 dry_run_check 口径）
- 负样本：negative_pairs.json 20 组无关查询，判定"过滤成功"= 阈值下 hits 返回空
- 输出每档阈值：正样本命中率 / 负样本过滤率，标注分界

用途：标定 KB_EMBEDDING_MIN_SCORE 的推荐区间（正样本不失真 + 负样本全滤掉）。
"""
import json
import os
import pathlib
import sys

os.environ["KB_BACKEND"] = "embedding"  # 必须在 import kb_loader 之前
PROJ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ))

import services.kb_embedding as kbe  # noqa: E402  模块加载即注册 embedding 后端
from services.kb_loader import retrieve_hits, retrieve_kb  # noqa: E402
from dry_run_check import K, answer_text, norm  # noqa: E402  复用评测口径

POS_DS = pathlib.Path(__file__).resolve().parent / "seed_pairs.json"
NEG_DS = pathlib.Path(__file__).resolve().parent / "negative_pairs.json"
THRESHOLDS = [None, 0.30, 0.40, 0.50, 0.55, 0.60, 0.62, 0.65, 0.70, 0.75, 0.80]


def _positive_pairs():
    ds = json.load(open(POS_DS, encoding="utf-8"))
    return [p for p in ds["pairs"] if p.get("status") != "graduated"]


def _negative_pairs():
    return json.load(open(NEG_DS, encoding="utf-8"))["negatives"]


def eval_one(threshold):
    """设置阈值，返回 (pos_hit_rate, neg_filter_rate, pos_details, neg_details)"""
    kbe._MIN_SCORE = threshold  # monkeypatch：_rank 读取模块全局，逐档生效
    pos = _positive_pairs()
    pos_hit, pos_total = 0, 0
    pos_missed = []
    for p in pos:
        kws = p.get("keywords", [])
        if not kws:
            continue
        fn = p["target"]["file"]
        res = retrieve_kb(kws, fn, top_k=K)
        ans = norm(answer_text(p))
        pos_total += 1
        if ans and ans in norm(res):
            pos_hit += 1
        else:
            pos_missed.append(p["id"])
    neg = _negative_pairs()
    neg_filtered, neg_total = 0, 0
    neg_unfiltered = []
    for n in neg:
        fn = n["file"]
        hits = retrieve_hits(n["keywords"], fn, top_k=K)
        neg_total += 1
        if not hits:
            neg_filtered += 1
        else:
            neg_unfiltered.append((n["id"], len(hits)))
    return pos_hit / pos_total, neg_filtered / neg_total, pos_missed, neg_unfiltered


if __name__ == "__main__":
    print(f"min_score 阈值评估（正样本 {len(_positive_pairs())} run 对 / 负样本 {len(_negative_pairs())} 组）\n")
    print(f"{'min_score':>10} | {'正样本命中':>10} | {'负样本过滤':>10} | 正样本丢失 / 负样本残留")
    print("-" * 80)
    results = []
    for t in THRESHOLDS:
        ph, nf, missed, unfiltered = eval_one(t)
        results.append((t, ph, nf))
        label = "无阈值" if t is None else f"{t:.2f}"
        miss_str = "、" .join(missed[:5]) + ("…" if len(missed) > 5 else "") if missed else "-"
        unf_str = str(unfiltered[:5]) + ("…" if len(unfiltered) > 5 else "") if unfiltered else "-"
        print(f"{label:>10} | {ph*100:>9.1f}% | {nf*100:>9.1f}% | {miss_str} / {unf_str}")

    # 分界：正样本 100% 命中下，负样本过滤率最高的阈值
    print("\n[分界分析]")
    best = None
    for t, ph, nf in results:
        if ph == 1.0:
            best = (t, ph, nf)
    if best:
        t, ph, nf = best
        label = "无阈值" if t is None else f"{t:.2f}"
        print(f"正样本保持 100% 命中时，负样本过滤率最高档: min_score={label}（过滤 {nf*100:.0f}%）")
    else:
        print("无任何档位保持正样本 100% 命中，需人工权衡误杀容忍度")
