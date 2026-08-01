#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""端到端 Function Calling 验证

真实用例 × 4：八字分析、紫微分析、验盘、交叉验证。
每个走完整链路 run_with_fc，评估三轮：
  (1) Tool 调用序列是否合理
  (2) 最终分析文本质量
  (3) 有没有漏调或误调

运行方式：
  python test_e2e_fc.py              # 全部四个
  python test_e2e_fc.py --bazi       # 仅八字
  python test_e2e_fc.py --ziwei      # 仅紫微
  python test_e2e_fc.py --verify     # 仅验盘
  python test_e2e_fc.py --cross      # 仅交叉验证
"""

import json
import sys
import os
import time
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.orchestrator import AnalysisOrchestrator

# ── 颜色 ──
G = '\033[92m'; R = '\033[91m'; Y = '\033[93m'; C = '\033[96m'; N = '\033[0m'; B = '\033[1m'

# ── 共享测试数据 ──
TEST_BIRTH = {
    "year": 2005, "month": 8, "day": 19, "hour": 1, "minute": 35,
    "gender": "男", "longitude": 113.75, "location": "广东省东莞市",
}

USER_ID = f"e2e_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

# ── System Prompts（精简的 function calling 版） ──

PROMPT_BAZI = """你是一位传统八字命理师。你可以调用以下工具来辅助分析：

1. paipan_bazi — 先排盘获取完整命盘数据（必须第一步调用）
2. wuxing_query — 查询五行属性和十神关系
3. kb_retrieve — 从八字知识库检索调候、格局、神煞等专业知识
4. memory_retrieve — 检索用户历史分析记录（分析前调用）
5. memory_store — 保存分析结论（分析完成后调用）

分析流程：先调 memory_retrieve 查历史 → 调 paipan_bazi 排盘 → 按需调 wuxing_query/kb_retrieve → 输出分析文本 → 调 memory_store 保存。

输出要求：
- 调用完所有需要的工具后，输出完整的八字分析
- 分析包含：日主五行、旺衰、格局、调候用神、十神分布、大运走势
- 基于工具返回的真实数据，不编造任何天干地支和五行属性"""

PROMPT_ZIWEI = """你是一位紫微斗数命理师。你可以调用以下工具来辅助分析：

1. paipan_ziwei — 先排盘获取十二宫星曜分布（必须第一步调用）
2. star_lookup — 查询星曜的五行属性和正负面特质
3. kb_retrieve — 从紫微知识库检索格局、宫位、星曜等专业知识
4. memory_retrieve — 检索用户历史分析记录（分析前调用）
5. memory_store — 保存分析结论（分析完成后调用）

分析流程：先调 memory_retrieve 查历史 → 调 paipan_ziwei 排盘 → 按需调 star_lookup/kb_retrieve → 输出分析文本 → 调 memory_store 保存。

输出要求：
- 调用完所有需要的工具后，输出完整的紫微斗数分析
- 分析包含：命宫主星、身宫位置、四化分布、格局判定、大限走势
- 基于工具返回的真实数据，不编造任何星曜和宫位信息"""

PROMPT_VERIFY = """你是一位命理验盘师。你可以调用以下工具来核查命盘准确性：

1. paipan_bazi — 八字排盘获取四柱、十神、大运等数据（先排盘拿到盘面数据才能验）
2. paipan_ziwei — 紫微排盘获取十二宫、星曜分布等数据
3. kb_retrieve — 从知识库检索验盘规范和信号规则
4. memory_retrieve — 检索用户历史分析记录（分析前调用）
5. memory_store — 保存验盘结论（分析完成后调用）

分析流程：先调 memory_retrieve 查历史 → 调 paipan_bazi 排盘拿到八字数据 → 调 kb_retrieve 获取信号规则 → 基于盘面信号提取可验证的人生事件 → 输出验盘分析 → 调 memory_store 保存。

如果用户提供了人生事实（如哪年升学/搬家/结婚等），逐一对照盘面信号验证。
如果用户未提供人生事实，基于盘面强信号倒推可验证事件，供用户确认。

输出要求：
- 调用完所有需要的工具后，输出验盘分析
- 每条信号标注置信度：高置信/中置信/低置信
- 明确指出验盘结论"""

PROMPT_CROSS = """你是一位命理综合分析专家。你可以调用以下工具进行八字与紫微的交叉验证：

1. paipan_bazi — 八字排盘
2. paipan_ziwei — 紫微排盘
3. wuxing_query — 五行十神查询
4. star_lookup — 星曜查询
5. kb_retrieve — 知识库检索（八字+紫微均可）
6. memory_retrieve — 检索用户历史分析记录（分析前调用）
7. memory_store — 保存分析结论（分析完成后调用）

分析流程：先调 memory_retrieve 查历史 → 同时调 paipan_bazi 和 paipan_ziwei 排盘 → 按需调 star_lookup/wuxing_query/kb_retrieve → 对比分析 → 调 memory_store 保存。

输出要求：
- 调用完所有需要的工具后，输出八字和紫微的交叉对比分析
- 标注两套体系的共识点和分歧点
- 基于工具返回的真实数据，不编造任何信息"""

# ── 评估框架 ──

def evaluate_tool_sequence(capability: str, tool_calls: list) -> dict:
    """评估 Tool 调用序列"""
    issues = []
    ok_points = []

    if not tool_calls:
        return {"pass": False, "issues": ["没有进行任何 Tool 调用"], "ok": [], "score": 0}

    calls_by_tool = {}
    for tc in tool_calls:
        tname = tc["tool"]
        calls_by_tool.setdefault(tname, []).append(tc)

    # 1. 第一步是否为排盘
    first_call = tool_calls[0]["tool"]
    paipan_tool = "paipan_bazi" if capability in ("bazi_analysis", "cross_validate") else "paipan_ziwei"

    if capability == "verify_panel":
        # 验盘需要先排盘拿到盘面数据
        if first_call in ("memory_retrieve", "paipan_bazi", "paipan_ziwei"):
            ok_points.append(f"验盘首调用正确: {first_call}")
        else:
            issues.append(f"验盘首调用不应是 {first_call}，应为 memory_retrieve 或排盘工具")
    else:
        if first_call in ("memory_retrieve", paipan_tool):
            ok_points.append(f"首调用合理: {first_call}")
        else:
            issues.append(f"首调用期望 memory_retrieve 或 {paipan_tool}，实际: {first_call}")

    # 2. 排盘类 tool 是否被调用
    if capability == "bazi_analysis":
        if "paipan_bazi" in calls_by_tool:
            ok_points.append("paipan_bazi 已调用")
        else:
            issues.append("缺少 paipan_bazi 排盘调用")

    elif capability == "ziwei_analysis":
        if "paipan_ziwei" in calls_by_tool:
            ok_points.append("paipan_ziwei 已调用")
        else:
            issues.append("缺少 paipan_ziwei 排盘调用")
        if "star_lookup" in calls_by_tool:
            ok_points.append("star_lookup 已调用（星曜查询）")

    elif capability == "cross_validate":
        if "paipan_bazi" in calls_by_tool:
            ok_points.append("paipan_bazi 已调用")
        else:
            issues.append("交叉验证缺少 paipan_bazi")
        if "paipan_ziwei" in calls_by_tool:
            ok_points.append("paipan_ziwei 已调用")
        else:
            issues.append("交叉验证缺少 paipan_ziwei")

    elif capability == "verify_panel":
        if "paipan_bazi" in calls_by_tool or "paipan_ziwei" in calls_by_tool:
            ok_points.append("排盘 tool 已调用（拿到盘面数据）")
        else:
            issues.append("验盘缺少排盘调用（无法获取盘面数据）")
        if "kb_retrieve" in calls_by_tool:
            ok_points.append("kb_retrieve 已调用（验盘规范检索）")

    # 3. 是否调用 memory_store 保存结果
    if "memory_store" in calls_by_tool:
        ok_points.append("memory_store 已调用（结果持久化）")
    # 注：不强求每次都要 memory_store，有些场景可能 LLM 判断不需要

    # 4. 是否有多余调用
    # 验盘现在可以调用排盘 tool

    # 5. 调用顺序
    if len(tool_calls) > 1:
        paipan_seen = False
        memory_store_seen = False
        for tc in tool_calls:
            if tc["tool"] in ("paipan_bazi", "paipan_ziwei"):
                paipan_seen = True
            elif tc["tool"] == "memory_store":
                memory_store_seen = True
            # 排盘之前不应调用依赖排盘结果的 tool
            if not paipan_seen and tc["tool"] in ("wuxing_query", "star_lookup"):
                issues.append(f"排盘前不应调用 {tc['tool']}（缺少排盘数据）")

    score = len(ok_points) / max(len(ok_points) + len(issues), 1)
    return {
        "pass": len(issues) == 0,
        "issues": issues,
        "ok": ok_points,
        "score": round(score * 100),
        "total_calls": len(tool_calls),
        "unique_tools": list(calls_by_tool.keys()),
    }


def evaluate_text_quality(text: str, capability: str) -> dict:
    """评估最终分析文本质量"""
    issues = []
    ok_points = []

    if not text or len(text) < 50:
        return {"pass": False, "issues": ["输出文本为空或过短"], "ok": [], "score": 0}

    # 通用检查
    if len(text) >= 200:
        ok_points.append(f"文本长度充足 ({len(text)} 字符)")
    else:
        issues.append(f"文本过短 ({len(text)} 字符)")

    # 八字分析关键词
    if capability == "bazi_analysis":
        bazi_keywords = ["日主", "五行", "天干", "用神", "格局", "大运"]
        found = [kw for kw in bazi_keywords if kw in text]
        ok_points.append(f"命中关键词: {found}")
        missed = [kw for kw in bazi_keywords if kw not in text]
        if missed:
            issues.append(f"缺少关键词: {missed}")

    # 紫微分析关键词
    elif capability == "ziwei_analysis":
        ziwei_keywords = ["命宫", "星", "宫", "四化", "大限"]
        found = [kw for kw in ziwei_keywords if kw in text]
        ok_points.append(f"命中关键词: {found}")
        missed = [kw for kw in ziwei_keywords if kw not in text]
        if missed:
            issues.append(f"缺少关键词: {missed}")

    # 验盘关键词
    elif capability == "verify_panel":
        verify_keywords = ["验盘", "验证", "信号", "置信", "准确"]
        found = [kw for kw in verify_keywords if kw in text]
        ok_points.append(f"命中关键词: {found}")
        if not found:
            issues.append("验盘文本缺少验盘相关关键词")

    # 交叉验证关键词
    elif capability == "cross_validate":
        cross_keywords = ["八字", "紫微", "对比", "交叉", "验证"]
        found = [kw for kw in cross_keywords if kw in text]
        ok_points.append(f"命中关键词: {found}")
        if len(found) < 2:
            issues.append("交叉验证缺少八字/紫微对比关键词")

    # 幻觉检测：是否出现无法验证的数据
    hallucination_patterns = [
        "据我推算", "我认为",  # 模糊词不是幻觉，但做标记
    ]
    # 不在本文做严格幻觉检测，避免误报

    score = len(ok_points) / max(len(ok_points) + len(issues), 1)
    return {
        "pass": len(issues) == 0,
        "issues": issues,
        "ok": ok_points,
        "score": round(score * 100),
        "text_len": len(text),
        "text_preview": text[:200] + ("..." if len(text) > 200 else ""),
    }


def run_single_test(orch: AnalysisOrchestrator, capability_name: str,
                    user_input: str, system_prompt: str,
                    user_message: str = None) -> dict:
    """执行单个端到端测试"""
    t0 = time.perf_counter()

    result = orch.run_with_fc(
        capability_name=capability_name,
        system_prompt=system_prompt,
        messages=[{"role": "user", "content": user_message or user_input}],
        max_rounds=8,
        max_tokens=8192,
        timeout=120,
    )

    elapsed = time.perf_counter() - t0

    if not result.get("success"):
        return {
            "success": False,
            "error": result.get("error", "Unknown"),
            "elapsed_s": round(elapsed, 1),
        }

    tool_calls = result.get("tool_calls", [])
    text = result.get("text", "")
    rounds = result.get("rounds", 0)
    finish_reason = result.get("finish_reason", "unknown")
    usage = result.get("usage", {})

    seq_eval = evaluate_tool_sequence(capability_name, tool_calls)
    text_eval = evaluate_text_quality(text, capability_name)

    # 漏调/误调检测
    missing_or_wrong = []
    if seq_eval["issues"]:
        missing_or_wrong.extend([f"序列问题: {i}" for i in seq_eval["issues"]])
    if text_eval["issues"]:
        missing_or_wrong.extend([f"文本问题: {i}" for i in text_eval["issues"]])

    return {
        "success": True,
        "capability": capability_name,
        "user_input": user_input,
        "elapsed_s": round(elapsed, 1),
        "rounds": rounds,
        "finish_reason": finish_reason,
        "tool_calls": [{
            "round": tc["round"],
            "tool": tc["tool"],
            "success": tc["success"],
            "elapsed_ms": round(tc.get("elapsed_ms", 0)),
        } for tc in tool_calls],
        "text_len": len(text),
        "text": text,
        "usage": usage,
        # 评估
        "tool_seq": seq_eval,
        "text_quality": text_eval,
        "overall_pass": seq_eval["pass"] and text_eval["pass"] and len(missing_or_wrong) == 0,
        "missing_or_wrong": missing_or_wrong,
    }


# ══════════════════════════════════════════════════════════
# 主测试
# ══════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bazi", action="store_true")
    parser.add_argument("--ziwei", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--cross", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    run_all = not (args.bazi or args.ziwei or args.verify or args.cross)
    to_run = []
    if run_all or args.bazi: to_run.append(("bazi_analysis", PROMPT_BAZI, "帮我分析八字格局和用神。出生日期2005年8月19日凌晨1点35分，广东东莞，男"))
    if run_all or args.ziwei: to_run.append(("ziwei_analysis", PROMPT_ZIWEI, "帮我排紫微斗数命盘并分析。出生日期2005年8月19日凌晨1点35分，广东东莞，男"))
    if run_all or args.verify: to_run.append(("verify_panel", PROMPT_VERIFY, "帮我验盘核对命盘准确性。出生日期2005年8月19日凌晨1点35分，广东东莞，男。基于盘面信号提取可验证事件，标注每条信号的置信度"))
    if run_all or args.cross: to_run.append(("cross_validate", PROMPT_CROSS, "帮我做八字和紫微的交叉综合分析。出生日期2005年8月19日凌晨1点35分，广东东莞，男"))

    print(f"\n{B}╔══════════════════════════════════════════════╗{N}")
    print(f"{B}║  🧪 端到端 Function Calling 验证            ║{N}")
    print(f"{B}║  4 用例 × 3 轮评估 = 12 项检查             ║{N}")
    print(f"{B}╚══════════════════════════════════════════════╝{N}")

    orch = AnalysisOrchestrator()
    orch.register_defaults()
    s = orch.summary()
    print(f"\n  Tool: {s['tools']['total']} | Capability: {s['capabilities']['total']} | Skill: {s['skills']['total']}")
    print(f"  User ID: {USER_ID}")

    overall_pass = 0
    overall_fail = 0
    all_results = []

    for cap_name, prompt, user_msg in to_run:
        print(f"\n{B}{'─' * 50}{N}")
        print(f"{B}  📋 {cap_name}{N}")
        print(f"{B}{'─' * 50}{N}")
        print(f"  输入: {user_msg[:80]}...")

        result = run_single_test(orch, cap_name, user_msg, prompt)

        if not result["success"]:
            print(f"  {R}❌ 执行失败: {result.get('error', 'Unknown')}{N}")
            overall_fail += 1
            all_results.append(result)
            continue

        # (1) Tool 调用序列
        seq = result["tool_seq"]
        print(f"\n  {C}(1) Tool 调用序列{N}  score={seq['score']}%")
        print(f"      总调用: {seq['total_calls']} 次 | 唯一 Tool: {seq['unique_tools']}")

        if seq["total_calls"] > 0:
            for tc in result["tool_calls"]:
                status = f"{G}✓{N}" if tc["success"] else f"{R}✗{N}"
                print(f"      R{tc['round']} {status} {tc['tool']} ({tc['elapsed_ms']}ms)")

        for ok in seq["ok"]:
            print(f"      {G}✅{N} {ok}")
        for issue in seq["issues"]:
            print(f"      {R}❌{N} {issue}")

        # (2) 文本质量
        txt = result["text_quality"]
        print(f"\n  {C}(2) 最终分析文本{N}  score={txt['score']}% | 长度={txt['text_len']}字")
        for ok in txt["ok"]:
            print(f"      {G}✅{N} {ok}")
        for issue in txt["issues"]:
            print(f"      {R}❌{N} {issue}")

        # (3) 漏调/误调
        mw = result["missing_or_wrong"]
        print(f"\n  {C}(3) 漏调/误调{N}  {'无问题 ✓' if not mw else f'{R}{len(mw)} 个问题{N}'}")
        for item in mw:
            print(f"      {R}⚠{N} {item}")

        print(f"\n  {B}结束原因:{N} {result['finish_reason']} | "
              f"{B}轮数:{N} {result['rounds']} | "
              f"{B}耗时:{N} {result['elapsed_s']}s | "
              f"{B}Token:{N} in={result['usage'].get('input_tokens', 0)} out={result['usage'].get('output_tokens', 0)}")

        all_results.append(result)
        if result["overall_pass"]:
            overall_pass += 1
        else:
            overall_fail += 1

    # ═══ 汇总 ═══
    print(f"\n{B}{'═' * 50}{N}")
    print(f"{B}  📊 汇总{N}")
    print(f"{B}{'═' * 50}{N}")

    total_tests = overall_pass + overall_fail
    for r in all_results:
        if not r.get("success"):
            print(f"  {R}❌{N} {r.get('capability', '?')}: API 失败 — {r.get('error', '')}")
            continue
        status = f"{G}✅{N}" if r["overall_pass"] else f"{R}❌{N}"
        print(f"  {status} {r['capability']} | "
              f"seq={r['tool_seq']['score']}% text={r['text_quality']['score']}% | "
              f"{r['tool_seq']['total_calls']}calls {r['rounds']}rounds {r['elapsed_s']}s")

    print(f"\n  {G}通过: {overall_pass}{N}  /  {R}失败: {overall_fail}{N}  /  总计: {total_tests}")

    # 保存详细报告
    report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              f"e2e_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    # 完整文本太长，只保存摘要和工具调用
    report = []
    for r in all_results:
        entry = {
            "capability": r.get("capability", "?"),
            "success": r.get("success", False),
            "elapsed_s": r.get("elapsed_s", 0),
        }
        if r.get("success"):
            entry["rounds"] = r["rounds"]
            entry["finish_reason"] = r["finish_reason"]
            entry["tool_calls"] = r["tool_calls"]
            entry["tool_seq_score"] = r["tool_seq"]["score"]
            entry["text_quality_score"] = r["text_quality"]["score"]
            entry["text_len"] = r["text_len"]
            entry["text"] = r["text"][:3000]  # 截取前3000字
            entry["issues"] = r["missing_or_wrong"]
            entry["usage"] = r.get("usage", {})
        else:
            entry["error"] = r.get("error", "")
        report.append(entry)

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n  详细报告: {report_path}")

    if overall_fail > 0:
        print(f"\n  {R}💥 有 {overall_fail} 项端到端测试未通过，详见上方评估{N}")
    else:
        print(f"\n  {G}🎉 所有端到端测试通过{N}")

    # 清理测试记忆
    try:
        mem_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "sessions", "user_profiles", f"{USER_ID}.json")
        if os.path.exists(mem_path):
            os.remove(mem_path)
    except Exception:
        pass

    return 0 if overall_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
