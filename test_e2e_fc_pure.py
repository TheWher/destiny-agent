# -*- coding: utf-8 -*-
"""e2e_fc 结构纯函数 pytest 轨（TODO-PAIPAN-PYTEST 挂账②，2026-08-06 韩湘生落）

从 test_e2e_fc.py 拆出的两个评估纯函数：
- evaluate_tool_sequence(capability, tool_calls) -> dict
- evaluate_text_quality(text, capability) -> dict

两者均为纯规则函数：输入 dict 进出，无 LLM 调用、无网络、无 IO，
pytest 直接构造输入覆盖全分支，不需要 mock（能纯规则直测就别造 mock，
mock 只替网络不替逻辑；真 E2E 编排层 run_with_fc 仍在 requires-llm 段单列）。

ids 规矩与 test_paipan 一致：每个 case 带可读 id，pytest 轨涨的每一格
按 id 清单逐格对照。
"""

import pytest

from test_e2e_fc import evaluate_tool_sequence, evaluate_text_quality

# ============================================================
# evaluate_tool_sequence：Tool 调用序列评估
# ============================================================

SEQ_CASES = [
    # ── 空调用 ──
    {
        "id": "seq-empty-calls",
        "desc": "没有任何 Tool 调用",
        "capability": "bazi_analysis",
        "tool_calls": [],
        "expect_pass": False,
        "expect_issues": ["没有进行任何 Tool 调用"],
    },
    # ── 首调用错误 ──
    {
        "id": "seq-bazi-first-call-wrong",
        "desc": "八字首调用是 wuxing_query（应 memory_retrieve 或 paipan_bazi）",
        "capability": "bazi_analysis",
        "tool_calls": [{"tool": "wuxing_query", "round": 1}],
        "expect_pass": False,
        "expect_issues": ["首调用期望 memory_retrieve 或 paipan_bazi，实际: wuxing_query"],
    },
    {
        "id": "seq-verify-first-call-wrong",
        "desc": "验盘首调用是 star_lookup（应 memory_retrieve 或排盘工具）",
        "capability": "verify_panel",
        "tool_calls": [{"tool": "star_lookup", "round": 1}],
        "expect_pass": False,
        "expect_issues": ["验盘首调用不应是 star_lookup，应为 memory_retrieve 或排盘工具"],
    },
    # ── 首调用正确路径 ──
    {
        "id": "seq-bazi-first-call-ok",
        "desc": "八字首调用 memory_retrieve 合法",
        "capability": "bazi_analysis",
        "tool_calls": [
            {"tool": "memory_retrieve", "round": 1},
            {"tool": "paipan_bazi", "round": 2},
            {"tool": "memory_store", "round": 3},
        ],
        "expect_pass": True,
        "expect_issues": [],
    },
    {
        "id": "seq-verify-first-call-ok",
        "desc": "验盘首调用 paipan_bazi 合法",
        "capability": "verify_panel",
        "tool_calls": [
            {"tool": "paipan_bazi", "round": 1},
            {"tool": "kb_retrieve", "round": 2},
        ],
        "expect_pass": True,
        "expect_issues": [],
    },
    # ── 缺排盘 ──
    {
        "id": "seq-bazi-missing-paipan",
        "desc": "八字缺 paipan_bazi",
        "capability": "bazi_analysis",
        "tool_calls": [{"tool": "memory_retrieve", "round": 1}],
        "expect_pass": False,
        "expect_issues": ["缺少 paipan_bazi 排盘调用"],
    },
    {
        "id": "seq-ziwei-missing-paipan",
        "desc": "紫微缺 paipan_ziwei",
        "capability": "ziwei_analysis",
        "tool_calls": [{"tool": "memory_retrieve", "round": 1}],
        "expect_pass": False,
        "expect_issues": ["缺少 paipan_ziwei 排盘调用"],
    },
    {
        "id": "seq-cross-missing-paipan",
        "desc": "交叉验证缺 paipan_ziwei（只排了八字）",
        "capability": "cross_validate",
        "tool_calls": [{"tool": "paipan_bazi", "round": 1}],
        "expect_pass": False,
        "expect_issues": ["交叉验证缺少 paipan_ziwei"],
    },
    {
        "id": "seq-verify-missing-paipan",
        "desc": "验盘无任何排盘调用",
        "capability": "verify_panel",
        "tool_calls": [{"tool": "memory_retrieve", "round": 1}],
        "expect_pass": False,
        "expect_issues": ["验盘缺少排盘调用（无法获取盘面数据）"],
    },
    # ── 排盘前调用依赖排盘结果的 tool（顺序检查）──
    {
        "id": "seq-wuxing-before-paipan",
        "desc": "八字排盘前调 wuxing_query",
        "capability": "bazi_analysis",
        "tool_calls": [
            {"tool": "wuxing_query", "round": 1},
            {"tool": "paipan_bazi", "round": 2},
        ],
        "expect_pass": False,
        "expect_issues": ["排盘前不应调用 wuxing_query（缺少排盘数据）"],
    },
    # ── 完整合法序列 ──
    {
        "id": "seq-ziwei-full-pass",
        "desc": "紫微完整合法序列：memory_retrieve → paipan_ziwei → star_lookup → memory_store",
        "capability": "ziwei_analysis",
        "tool_calls": [
            {"tool": "memory_retrieve", "round": 1},
            {"tool": "paipan_ziwei", "round": 2},
            {"tool": "star_lookup", "round": 3},
            {"tool": "memory_store", "round": 4},
        ],
        "expect_pass": True,
        "expect_issues": [],
    },
]


@pytest.mark.parametrize("case", SEQ_CASES, ids=[c["id"] for c in SEQ_CASES])
def test_tool_sequence(case):
    result = evaluate_tool_sequence(case["capability"], case["tool_calls"])
    assert result["pass"] is case["expect_pass"], (
        f"[{case['id']}] pass 期望 {case['expect_pass']} 实际 {result['pass']}，issues: {result['issues']}"
    )
    if case["expect_issues"]:
        assert result["issues"], f"[{case['id']}] 期望有 issues 实际为空"
        for expected in case["expect_issues"]:
            assert expected in result["issues"], (
                f"[{case['id']}] 期望 issue 「{expected}」 实际 issues: {result['issues']}"
            )
    else:
        assert not result["issues"], f"[{case['id']}] 期望无 issues 实际: {result['issues']}"


# ============================================================
# evaluate_text_quality：最终分析文本质量评估
# ============================================================

TXT_CASES = [
    # ── 空文本 / 过短 ──
    {
        "id": "txt-empty",
        "desc": "空文本",
        "capability": "bazi_analysis",
        "text": "",
        "expect_pass": False,
        "expect_issues": ["输出文本为空或过短"],
    },
    {
        "id": "txt-short",
        "desc": "文本不足 50 字",
        "capability": "bazi_analysis",
        "text": "这个八字还可以。",
        "expect_pass": False,
        "expect_issues": ["输出文本为空或过短"],
    },
    {
        "id": "txt-len-under-200",
        "desc": "文本 50~200 字：过短 issue（关键词全命中，唯一 issue 是长度）",
        "capability": "ziwei_analysis",
        "text": "命宫主星太阳，身宫落在官禄宫。四化分布整体均匀，化禄在财帛宫，化权在官禄宫，化科在命宫。此盘格局中等偏上，大限走势先抑后扬。命宫星曜组合有力，财官双美，晚运安泰。",
        "expect_pass": False,
        "expect_issues": ["文本过短"],
    },
    # ── 关键词缺失 ──
    {
        "id": "txt-bazi-missing-keywords",
        "desc": "八字文本 200+ 字但不含日主/五行/天干/用神/格局/大运",
        "capability": "bazi_analysis",
        "text": "你的命很好，运势不错，这一年会有好事发生，财运方面也有不错的进账。整体来看你性格稳重，做事有耐心，朋友缘也不错，事业上会有贵人相助。最近几年运势稳步上升，尤其是在合作方面会有新的机会。健康方面要注意作息，饮食清淡一些更好。感情上顺其自然即可，不用过于强求。家里的长辈对你帮助很大，多听他们的建议会有好处。下半年适合稳扎稳打，不宜冒进。今年秋天开始，正财运逐渐走强，适合做中长期规划。学习方面保持专注会有突破，工作上主动一点机会更多。家庭运势平稳，出行顺利，整体是向上的一年。",
        "expect_pass": False,
        "expect_issues": ["缺少关键词"],
    },
    {
        "id": "txt-verify-missing-keywords",
        "desc": "验盘文本 200+ 字但不含验盘/验证/信号/置信/准确",
        "capability": "verify_panel",
        "text": "你今年运势不错，事业上会有稳步进展，同事关系融洽，领导对你印象良好。财务方面收支平衡，年底会有一笔计划内的收入。家庭生活和谐，与家人相处愉快，孩子学业进步明显。健康上保持规律运动，精神状态很好，睡眠质量不错。出行方面一切顺利，远方有故人来访，带来好消息。下半年适合推进搁置已久的计划，时机成熟，水到渠成。注意避免冲动消费，理财以稳健为主。人际关系上广结善缘，贵人多在南方。整体来看，这一年是平稳向上的一年，把握住机会即可。",
        "expect_pass": False,
        "expect_issues": ["验盘文本缺少验盘相关关键词"],
    },
    {
        "id": "txt-cross-missing-keywords",
        "desc": "交叉验证文本 200+ 字但八字/紫微/对比/交叉/验证命中不足 2 个",
        "capability": "cross_validate",
        "text": "整体来看，你的人生运势处于上升通道，早年打下的基础正在逐渐兑现。事业上宜守宜攻，守的是现有优势，攻的是新领域的尝试。性格沉稳，执行力强，遇到困难不轻言放弃。财富运势平稳，正财为主，偏财不宜强求。健康方面注意脾胃，饮食规律即可。感情上成熟理性，与伴侣互相扶持，关系稳定。学业事业双线并进，贵人助力明显。未来三年是关键期，宜提前规划，稳中求进。家庭和睦，长辈安康，后辈聪慧。生活节奏宜张弛有度，工作之余给自己留出充电时间。整体运势向好，值得期待。",
        "expect_pass": False,
        "expect_issues": ["交叉验证缺少八字/紫微对比关键词"],
    },
    # ── 完整达标 ──
    {
        "id": "txt-bazi-full-pass",
        "desc": "八字文本关键词全命中且长度充足（200+ 字）",
        "capability": "bazi_analysis",
        "text": "日主乙木，生于申月，金旺木衰，五行以水木为用。天干透甲木，格局为伤官配印，贵气暗藏。"
               "调候用神取壬水润局，十神分布均衡，偏财正印相生有情。大运走势由西向东，早年奔波，"
               "中年运势渐入佳境，晚运丰隆。命局中财星得地，官星清透，事业上宜从事教育文化或专业技术之业。"
               "性格上外柔内刚，善谋略而不失分寸。流年层面，当前大运与命局形成良好互动，正是发展事业的黄金时期，"
               "宜把握机会，不宜观望。综合来看，此局清透有力，喜用得力，一生富贵层次中上。",
        "expect_pass": True,
        "expect_issues": [],
    },
    {
        "id": "txt-ziwei-full-pass",
        "desc": "紫微文本关键词全命中且长度充足（200+ 字）",
        "capability": "ziwei_analysis",
        "text": "命宫主星太阳，身宫在官禄宫，日月并明之格。四化分布：化禄在财帛宫，化权在官禄宫，"
               "化科在命宫，化忌在疾厄宫。命宫星曜组合有力，太阳庙旺，三方四正会照天梁、巨门。"
               "大限走势先抑后扬，早年较劳，中年后贵人显现。此盘格局层次中上，财官双美，"
               "适合从事公职或大型机构，晚运安泰。星曜五行配置均衡，命身宫联动良好，"
               "福德宫见天同，心态平和，福泽深厚。四化入命财官三宫，一生机遇多，把握得当可成大器。"
               "流年吉凶看四化引动，此命主贵而不富，宜以名求利，稳步发展。",
        "expect_pass": True,
        "expect_issues": [],
    },
]


@pytest.mark.parametrize("case", TXT_CASES, ids=[c["id"] for c in TXT_CASES])
def test_text_quality(case):
    result = evaluate_text_quality(case["text"], case["capability"])
    assert result["pass"] is case["expect_pass"], (
        f"[{case['id']}] pass 期望 {case['expect_pass']} 实际 {result['pass']}，issues: {result['issues']}"
    )
    if case["expect_issues"]:
        assert result["issues"], f"[{case['id']}] 期望有 issues 实际为空"
        for expected in case["expect_issues"]:
            assert any(expected in i for i in result["issues"]), (
                f"[{case['id']}] 期望 issue 含「{expected}」 实际 issues: {result['issues']}"
            )
    else:
        assert not result["issues"], f"[{case['id']}] 期望无 issues 实际: {result['issues']}"
