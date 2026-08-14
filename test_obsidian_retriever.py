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


def test_outcome_grades_per_hit_level():
    """结局梯度 per-hit 定级（2026-08-14 补）：证据包 meta 必须带行级梯度标签

    背景：rev2 措辞「命中条目自带梯度标签」数据层永不成立（evidence_pack 无 per-hit 标签，
    meta 只挂完整 L1-L4 词表），严格照做恒中性。修复：工具侧扫含查询词的行，
    命中结局词即挂 outcome_grades_level（机器定级，级别从重到轻+词长降序防子串冲突）。
    """
    from services.orchestrator import AnalysisOrchestrator
    import json

    orch = AnalysisOrchestrator()
    orch.register_defaults()

    # 命例体结局词：p466 古峯僧命 → L4_修辞型；p491 吕太后命 → L4_死亡终局
    for q, expect in [('其数安能逃哉', 'L4_修辞型'), ('夀終', 'L4_死亡终局')]:
        r = orch.tools.call('kb_obsidian_retrieve', query=q, top_k=3)
        assert r.success, r.error
        packs = json.loads(r.data['text'])
        assert any(
            p['meta'].get('outcome_grades_level') == expect
            for p in packs
        ), f"{q}: 未找到 {expect} 定级，实际={[p['meta'].get('outcome_grades_level') for p in packs]}"

    # 赋体段无结局词（禄逢冲破：吉处藏凶非词表词）→ 中性兜底，不得被全文别处污染
    r = orch.tools.call('kb_obsidian_retrieve', query='禄逢冲破', top_k=5)
    packs = json.loads(r.data['text'])
    for p in packs:
        assert 'outcome_grades_level' not in p['meta'], \
            f"{p['file']}: 禄逢冲破段不应被全文别处结局词污染"


def test_raw_exemption_limited_to_ancient():
    """raw 豁免只给古籍权威层：top5 不允许出现非古籍权威的 raw（防豁免范围扩大）
    注：digested 优先（+20）是既有机制未改动，此处钉的是修复边界"""
    hits = _hits('禄逢冲破')
    for h in hits:
        if h['status'] == 'raw':
            assert any(level in (h.get('authority') or '') for level in ANCIENT), \
                f"非古籍权威的 raw 被豁免浮上来了: {h['title']}"
