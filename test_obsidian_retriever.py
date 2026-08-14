# -*- coding: utf-8 -*-
"""检索层回归三柱（2026-08-14 质检后补）

柱子：
1. 古籍权威（古籍原文/古籍数字化平台）能进默认 top5
2. 消歧页提权：四化 → 消歧页第一
3. digested 优先于 raw（同 query 下无 raw 排在 digested 之前）

背景：质检发现 raw -20 惩罚压过 authority 优势，古籍原文 raw 快照被埋出 top5；
authority 精确匹配漏掉带括号变体，全部垫底。修复后此文件应全绿。
"""
import pytest
from knowledge_base.obsidian_retriever import retrieve

ANCIENT = {'古籍原文', '古籍数字化平台'}


def _hits(q, top_k=5):
    return [h for _s, h in retrieve(q, top_k=top_k)]


def test_ancient_text_in_top5():
    """古籍权威层必须出现在「禄逢冲破」默认 top5（当前全覽 -21 rank8，必红）"""
    hits = _hits('禄逢冲破')
    assert any(any(level in (h.get('authority') or '') for level in ANCIENT) for h in hits), \
        [h['title'] for h in hits]


def test_sihua_disambiguation_first():
    """「四化」默认 top1 必须是消歧页"""
    hits = _hits('四化')
    assert hits and hits[0]['type'] == 'disambiguation', [h['title'] for h in hits]


def test_raw_exemption_limited_to_ancient():
    """raw 豁免只给古籍权威层：top5 不允许出现非古籍权威的 raw（防豁免范围扩大）
    注：digested 优先（+20）是既有机制未改动，此处钉的是修复边界"""
    hits = _hits('禄逢冲破')
    for h in hits:
        if h['status'] == 'raw':
            assert any(level in (h.get('authority') or '') for level in ANCIENT), \
                f"非古籍权威的 raw 被豁免浮上来了: {h['title']}"
