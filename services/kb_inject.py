#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""知识库注入层 — 检索 hits → join annotations sidecar → 分层呈现。

同源原则（无假出处断言第三条的结构化实现）：
注入内容严格按 retrieve_hits 命中名单取，prompt 里出现的引文必然来自
annotations[命中条目]；source_truth=转述 的条目以按语呈现、禁止引号格式，
假出处从"LLM 不编"变成"结构上编不出来"。

裁剪规则（条件式，防 zc_ 纯提问裁空）：
- plate_ctx 非空 且 set(keywords) ∩ plate_ctx 非空 → 裁剪到交集（命中顺序保持）
- 否则（无上下文 / 关键词与命盘无交集）→ hits 全量 top_k，不裁
- 兜底：裁剪结果为空 → 回退全量，宁多勿空

2026-08-01 注入层（检索→注入→呈现同源）
"""
import json
import os

from services.kb_loader import retrieve_hits

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ANNOTATIONS_PATH = os.path.join(_ROOT, "knowledge_base", "ziwei_classics_annotations.json")
_annotations_cache: dict | None = None


def _load_annotations() -> dict:
    global _annotations_cache
    if _annotations_cache is None:
        try:
            with open(_ANNOTATIONS_PATH, encoding="utf-8") as f:
                _annotations_cache = json.load(f)
        except Exception:
            _annotations_cache = {}
    return _annotations_cache


def _render_block(name: str, a: dict) -> dict:
    """按 source_truth 分层呈现：原文/混合 → 引文格式（带出处）；转述 → 按语（不带引号）。"""
    st = a.get("source_truth", "转述")
    quotes = a.get("quotes") or []
    note = a.get("note", "")
    quote_text = quotes[0].get("text", "") if quotes else ""
    quote_src = quotes[0].get("source", "") if quotes else ""

    if st == "原文" and quote_text:
        presentation = f"【{name}】引文：『{quote_text}』（{quote_src}）"
    elif st == "混合" and quote_text:
        presentation = f"【{name}】引文：『{quote_text}』（{quote_src}）按语：{note}"
    else:
        presentation = f"【{name}】{note}"
    return {"name": name, "presentation": presentation, "source_truth": st}


def join_classics(
    keywords: list[str],
    plate_ctx: set[str] | None = None,
    top_k: int = 5,
) -> list[dict]:
    """检索 classics 并 join annotations sidecar，返回结构化注入块（按命中顺序）。

    Args:
        keywords: 检索关键词（格局名 / 星名等）
        plate_ctx: 允许呈现的条目名集合（对 classics 即命盘格局名集合，须与 hits 条目类型
            对齐；星/宫名集合会因类型不对齐而恒为空交集，裁剪自动失效回退全量）。
            None 或与 hits 无交集时不做裁剪。
        top_k: 检索返回条数

    Returns:
        [{"name", "presentation", "source_truth"}, ...]，按命中顺序。
    """
    hits = retrieve_hits(keywords, "ziwei_classics.json", top_k=top_k)
    # 条件式裁剪：hits 与命盘上下文有交集才裁（防 zc_ 纯提问把命中裁空）
    if plate_ctx is not None:
        cropped = [h for h in hits if h in plate_ctx]
        if cropped:  # 兜底：∩ 为空则回退全量，宁多勿空
            hits = cropped

    ann = _load_annotations()
    blocks = []
    for name in hits:
        a = ann.get(name)
        if not a:
            continue
        blocks.append(_render_block(name, a))
    return blocks


def join_classics_str(
    keywords: list[str],
    plate_ctx: set[str] | None = None,
    top_k: int = 5,
) -> str:
    """join_classics 的文本出口（直接拼进 prompt 用）。"""
    blocks = join_classics(keywords, plate_ctx, top_k)
    if not blocks:
        return ""
    # 口径声明（2026-08-04 加）：古籍原文可能含与引擎冲突的流派口径（庚干四化/铃星顺逆/五行局/晚子时等），
    # 注入时显式声明引擎优先，防 LLM 用古籍数值"纠正"盘面（RAG 口径过滤的轻量版）
    prefix = "（以下为古籍原文节选，流派口径可能与引擎不同。引用时只取意象与断法，具体安星/四化/数值一律以引擎数据为准，不引用古籍数值纠正盘面。）"
    return prefix + "\n" + "\n".join(b["presentation"] for b in blocks)
