# -*- coding: utf-8 -*-
"""classics str 出口真伪分层回归（2026-09-09 补残洞）。

残洞：str 出口（kb_retrieve 工具链）此前 generic 裸 dump 引文按语混写串，
转述条目带「引号」外观可被 LLM 当原文引用——与注入层 join_classics_str 的
「假出处结构上编不出来」承诺矛盾。现所有出口同源按 source_truth 分层。
"""
import pytest

from services.kb_loader import retrieve_kb, _format_classics_truth
from services.kb_inject import _load_annotations


REAL = "紫府同宫"


def test_yuanwen_entry_keeps_quote_format():
    """原文条目：引文格式带书名号引号+出处（标注状态可查）"""
    ann = _load_annotations()
    assert ann.get(REAL, {}).get("source_truth") == "原文", "标定前提：紫府同宫=原文"
    out = retrieve_kb([REAL], "ziwei_classics.json", top_k=3)
    assert REAL in out
    assert "『" in out and "』" in out, f"原文条目应保留引文格式: {out}"


def test_zhuanShu_entry_strips_quote_masquerade():
    """转述条目：不得再以引文格式裸奔（23 条转述抽样验证）"""
    ann = _load_annotations()
    zhuan = [n for n, a in ann.items() if a.get("source_truth") == "转述"]
    assert len(zhuan) >= 20, "标定前提：转述条目应≥20"
    leaked = []
    for name in zhuan[:5]:
        out = retrieve_kb([name], "ziwei_classics.json", top_k=1)
        # 分层后呈现以【名】开头；转述走按语路径（无『』引文）
        if "『" in out:
            leaked.append(name)
    assert not leaked, f"转述条目仍以引文格式呈现: {leaked}"


def test_missing_annotation_marked_not_silent():
    """sidecar 缺条目：显式标「出处未标注」，不静默裸奔"""
    kb = {"patterns": {"测试格": "某断语文本"}}
    fake_ann = {}
    import services.kb_inject as inj
    old = inj._annotations_cache
    inj._annotations_cache = fake_ann
    try:
        out = _format_classics_truth(kb, ["测试格"], top_k=3)
    finally:
        inj._annotations_cache = old
    assert "出处未标注" in out
    assert "不得作原文引用" in out


def test_hits_str_consistency_kept():
    """同源一致：hits 名单与 str 呈现条目一一对应（出口改造不得破坏契约）"""
    from services.kb_loader import retrieve_hits
    kws = ["紫微", "天府"]
    hits = retrieve_hits(kws, "ziwei_classics.json", top_k=5)
    out = retrieve_kb(kws, "ziwei_classics.json", top_k=5)
    for name in hits:
        assert name in out, f"hits 条目 {name} 未出现在 str 呈现中"
