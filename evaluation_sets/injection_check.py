#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""注入层级断言：对每对 seed_pairs 跑 join_classics，验证同源链（检索→注入→呈现）。

对齐口径（2026-08-01 韩湘生 / 春鳥橋 对撞）：
1. block.name ∈ retrieve_hits 名单（注入严格由 hits 产生，结构上编不出假出处）
2. source_truth ∈ {原文, 混合} → presentation 必含『』引文，引文文本 = annotations quotes[0].text，
   出处非空（引文有真实出处）
3. source_truth == 转述 → presentation 零『』（按语呈现，禁止引号格式）
4. 数据合法性：原文/混合必须有 quotes（渲染不变量；韩湘生全量 40 格局扫过『』只出现在原文/混合）
5. block.name ∈ annotations（sidecar 有记录才呈现）

非 classics query（zp/zh/zf）调 join_classics 命中含关键词的格局（如"紫微"→紫府同宫）
产生引文是合法行为，不挂"必须命中 target"。断言只查结构合法性。

裁剪行为（独立用例，验证条件式裁剪）：
A. plate_ctx 与 hits 有交集 → 只呈现交集内 name（命中顺序保持）
B. plate_ctx 与 hits 无交集 → 回退全量（宁多勿空，zc_ 纯提问路径）
"""
import json
import pathlib
import re
import sys

PROJ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ))
from services.kb_inject import join_classics  # noqa: E402
from services.kb_loader import retrieve_hits  # noqa: E402

DS = pathlib.Path(__file__).resolve().parent / "seed_pairs.json"
ANNOTATIONS = json.load(open(PROJ / "knowledge_base" / "ziwei_classics_annotations.json", encoding="utf-8"))
K = 5

_QUOTE_RE = re.compile(r"『(.+?)』")


def check_block(block: dict, hits: list) -> tuple[list[str], str | None]:
    """返回 (violations, data_issue)。data_issue 非 None 表示数据标注问题（非代码问题）。"""
    v = []
    name = block["name"]
    presentation = block["presentation"]
    st = block["source_truth"]
    a = ANNOTATIONS.get(name)

    # 断言 1：注入严格由 hits 产生
    if name not in hits:
        v.append(f"name {name!r} not in hits 名单")
    # 断言 5：sidecar 有记录
    if a is None:
        v.append(f"name {name!r} 不在 annotations")
        return v, None

    quotes = a.get("quotes") or []
    quoted = _QUOTE_RE.findall(presentation)

    if st in ("原文", "混合"):
        if not quotes:
            return v, f"{name}: source_truth={st} 但 quotes 空（数据标注问题，渲染已防御降级）"
        if not quoted:
            v.append(f"{name}: source_truth={st} 但 presentation 无『』引文")
        elif quoted[0] != quotes[0].get("text", ""):
            v.append(f"{name}: 引文文本 ≠ annotations quotes[0].text")
        if not quotes[0].get("source"):
            v.append(f"{name}: quotes[0].source 为空（引文无出处）")
    else:  # 转述
        if quoted:
            v.append(f"{name}: source_truth=转述 但 presentation 含『』引文")
    return v, None


def run_pairs() -> dict:
    ds = json.load(open(DS, encoding="utf-8"))
    pairs = ds["pairs"]
    stats = {"total": len(pairs), "with_blocks": 0, "violations": 0, "data_issues": 0}
    violations, data_issues = [], []
    for p in pairs:
        kws = p.get("keywords", [])
        if not kws:
            continue
        blocks = join_classics(kws, plate_ctx=None, top_k=K)
        if blocks:
            stats["with_blocks"] += 1
        hits = retrieve_hits(kws, "ziwei_classics.json", top_k=K)
        for b in blocks:
            vs, di = check_block(b, hits)
            for v in vs:
                violations.append(f"{p['id']}: {v}")
            if di:
                data_issues.append(f"{p['id']}: {di}")
    stats["violations"] = len(violations)
    stats["data_issues"] = len(data_issues)
    return {"stats": stats, "violations": violations, "data_issues": data_issues}


def run_cropping_cases() -> list[str]:
    """条件式裁剪行为验证：有交集裁、无交集回退全量。"""
    results = []
    # A. 有交集：keywords 命中 月朗天门，plate_ctx 含月朗天门 → 裁剪到交集
    kws = ["月朗天门"]
    ctx = {"月朗天门", "紫府同宫"}
    blocks = join_classics(kws, plate_ctx=ctx, top_k=K)
    names = [b["name"] for b in blocks]
    ok_a = names == ["月朗天门"]
    results.append(f"A 有交集裁剪: hits∩ctx={names} -> {'PASS' if ok_a else 'FAIL'}")
    # B. 无交集：plate_ctx 不含命中格局 → 回退全量（宁多勿空）
    ctx2 = {"无关格局甲", "无关格局乙"}
    blocks2 = join_classics(kws, plate_ctx=ctx2, top_k=K)
    hits = retrieve_hits(kws, "ziwei_classics.json", top_k=K)
    names2 = [b["name"] for b in blocks2]
    ok_b = set(names2) == (set(hits) & set(ANNOTATIONS.keys())) or (names2 and names2 == [b["name"] for b in join_classics(kws, top_k=K)])
    results.append(f"B 无交集回退全量: hits={hits[:2]}... 呈现={names2[:3]}... -> {'PASS' if ok_b else 'FAIL'}")
    # C. plate_ctx=None（纯提问默认）→ 全量不裁
    blocks3 = join_classics(kws, plate_ctx=None, top_k=K)
    names3 = [b["name"] for b in blocks3]
    ok_c = names3 and names3[0] == hits[0] if hits else names3 == []
    results.append(f"C plate_ctx=None 全量: 首条呈现={names3[0] if names3 else None} hits首条={hits[0] if hits else None} -> {'PASS' if ok_c else 'FAIL'}")
    return results


if __name__ == "__main__":
    res = run_pairs()
    s = res["stats"]
    print(f"[注入层级断言] pairs={s['total']} 产生引文块的对数={s['with_blocks']}")
    print(f"结构违规={s['violations']} 数据标注问题={s['data_issues']}")
    if res["violations"]:
        print("\n结构违规（代码/契约问题）:")
        for v in res["violations"]:
            print(f"  {v}")
    if res["data_issues"]:
        print("\n数据标注问题（非代码问题）:")
        for d in res["data_issues"]:
            print(f"  {d}")
    print("\n[裁剪行为]")
    for r in run_cropping_cases():
        print(f"  {r}")
    sys.exit(1 if s["violations"] else 0)
