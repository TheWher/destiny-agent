#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""编排层集成测试 — Tool 注册 · Capability 路由 · 端到端执行"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.orchestrator import (
    AnalysisOrchestrator, IntentRouter,
    ToolRegistry, CapabilityRegistry,
    ToolDef, CapabilityDef,
    ToolResult, CapabilityResult,
)

# ── 颜色 ──
G = '\033[92m'; R = '\033[91m'; Y = '\033[93m'; N = '\033[0m'; B = '\033[1m'

pass_count = 0; fail_count = 0; total = 0

def check(name, condition, detail=''):
    global pass_count, fail_count, total
    total += 1
    if condition:
        pass_count += 1; print(f'{G}✅{N} [{name}] {detail}')
    else:
        fail_count += 1; print(f'{R}❌{N} [{name}] {detail}')


# ══════════════════════════════════════════════════════════
# 1. 注册表基础测试
# ══════════════════════════════════════════════════════════

print(f"\n{B}═══ 1. 注册表基础 ═══{N}\n")

orch = AnalysisOrchestrator()
orch.register_defaults()

# Tool 注册数
s = orch.summary()
check("Tool 注册数 = 5", s['tools']['total'] == 5,
      f"实际: {s['tools']['total']}")
check("Tool 分类: paipan=2", s['tools']['by_category'].get('paipan') == 2)
check("Tool 分类: query=3", s['tools']['by_category'].get('query') == 3)

# Capability 注册数
check("Capability 注册数 = 4", s['capabilities']['total'] == 4,
      f"实际: {s['capabilities']['total']}")
expected_caps = ['bazi_analysis', 'ziwei_analysis', 'verify_panel', 'cross_validate']
for cap_name in expected_caps:
    check(f"Capability 存在: {cap_name}",
          cap_name in s['capabilities']['names'])

# 幂等注册
orch.register_defaults()
s2 = orch.summary()
check("重复注册不重复添加 Tool",
      s2['tools']['total'] == s['tools']['total'])
check("重复注册不重复添加 Capability",
      s2['capabilities']['total'] == s['capabilities']['total'])


# ══════════════════════════════════════════════════════════
# 2. Tool 执行测试
# ══════════════════════════════════════════════════════════

print(f"\n{B}═══ 2. Tool 执行 ═══{N}\n")

# star_lookup
r = orch.tools.call("star_lookup", star_name="紫微")
check("star_lookup(紫微) 成功", r.success)
check("star_lookup(紫微) 返回数据", r.data and '紫微' in r.data)
check("star_lookup(紫微) 五行=土",
      r.data.get('紫微', {}).get('element') == '土' if r.success else False)

r = orch.tools.call("star_lookup", stars=["天同", "太阴"])
check("star_lookup(天同|太阴) 成功", r.success)
check("star_lookup(天同|太阴) 返回 ≥2 条",
      r.success and len(r.data) >= 2 if r.success else False,
      f"实际: {len(r.data) if r.success and r.data else 0}")

# kb_retrieve
r = orch.tools.call("kb_retrieve", query="天府 财帛",
                    kb_name="ziwei_star_palace.json", top_k=3)
check("kb_retrieve 成功", r.success)
check("kb_retrieve 返回非空文本",
      r.success and len(r.data.get('text', '')) > 100 if r.success else False)

# wuxing_query
r = orch.tools.call("wuxing_query", ri_gan="甲", target_gan="庚")
check("wuxing_query(甲→庚) 成功", r.success)
check("wuxing_query(甲→庚) 十神=七杀",
      r.data.get('shishen') == '七杀' if r.success else False)

# 不存在的 Tool
r = orch.tools.call("nonexistent_tool")
check("不存在的 Tool 返回失败", not r.success)
check("不存在的 Tool 有错误信息", 'not found' in (r.error or ''))


# ══════════════════════════════════════════════════════════
# 3. IntentRouter 路由测试
# ══════════════════════════════════════════════════════════

print(f"\n{B}═══ 3. IntentRouter 路由 ═══{N}\n")

router = orch.router

# 单意图
check("「八字格局用神」→ bazi_analysis",
      router.resolve("帮我看看八字格局和用神") == "bazi_analysis")
check("「紫微命盘」→ ziwei_analysis",
      router.resolve("排个紫微斗数命盘看看") == "ziwei_analysis")
check("「验盘」→ verify_panel",
      router.resolve("验盘，帮我确认一下对不对") == "verify_panel")
check("「八字紫微一起」→ cross_validate",
      router.resolve("八字和紫微一起综合分析") == "cross_validate")

# 无关输入
check("「今天天气」→ None",
      router.resolve("今天天气不错") is None)

# resolve_all 多路匹配
all_matched = router.resolve_all("帮我全面完整系统地看一下")
names = [n for n, _ in all_matched]
check("「全面分析」多路匹配包含 cross_validate",
      "cross_validate" in names)
check("「全面分析」至少匹配 1 个",
      len(all_matched) >= 1,
      f"实际: {len(all_matched)} → {all_matched}")

# match 返回格式
m = router.match("紫微斗数命盘")
check("match 返回非空列表", len(m) > 0)
check("match 返回 (str, float) 元组",
      len(m[0]) == 2 and isinstance(m[0][0], str) and isinstance(m[0][1], float))

# 自定义关键词
custom = IntentRouter(keywords={"test_cap": ["测试", "验证"]})
check("自定义关键词路由",
      custom.resolve("跑一个测试") == "test_cap")
check("自定义关键词无关输入",
      custom.resolve("吃了吗") is None)


# ══════════════════════════════════════════════════════════
# 4. 排盘 Tool 测试（需要 bazi_calculator）
# ══════════════════════════════════════════════════════════

print(f"\n{B}═══ 4. 排盘 Tool ═══{N}\n")

r = orch.tools.call("paipan_bazi", year=2005, month=8, day=19,
                    hour=1, minute=35, gender="男",
                    longitude=113.75, location="广东省东莞市",
                    apply_solar_correction=False)
check("paipan_bazi 成功", r.success,
      f"error: {r.error}" if not r.success else "")
check("paipan_bazi 返回四柱",
      r.success and 'pillars' in r.data if r.success else False)
check("paipan_bazi 返回大运",
      r.success and 'dayun' in r.data and len(r.data['dayun']) > 0 if r.success else False)
check("paipan_bazi 日柱长度=2",
      r.success and len(r.data['pillars'].get('day', {}).get('gz', '')) == 2 if r.success else False)
check("paipan_bazi 时柱包含天干地支",
      r.success and 'gz' in r.data['pillars'].get('hour', {}) if r.success else False)

r = orch.tools.call("paipan_ziwei", year=2005, month=8, day=19,
                    hour=1, minute=35, gender="男")
check("paipan_ziwei 成功", r.success,
      f"error: {r.error}" if not r.success else "")
check("paipan_ziwei 返回十二宫",
      r.success and 'palaces' in r.data and len(r.data['palaces']) == 12 if r.success else False)
check("paipan_ziwei 返回四化",
      r.success and 'year_mutagens' in r.data if r.success else False)


# ══════════════════════════════════════════════════════════
# 5. Capability 端到端执行（不调用 LLM，验证路由和参数传递）
# ══════════════════════════════════════════════════════════

print(f"\n{B}═══ 5. Capability 路由执行（无 LLM）═══{N}\n")

# 验证 Capability 可以正确接收参数并调用底层函数
# 不需要真实 API Key，验证框架层面的参数传递和错误处理

# route 方法在没有 plate_dict 时应该返回错误（底层函数需要数据）
result = orch.route("帮我排八字")
check("route 无 plate_dict 返回失败", not result.success,
      f"实际: success={result.success}")
check("route 无 plate_dict 有错误信息",
      result.error is not None and len(result.error) > 0 if not result.success else False)

# route_all 同理
results = orch.route_all("全面分析一下")
check("route_all 无 plate_dict 返回列表", isinstance(results, list))
check("route_all 至少 1 个结果", len(results) >= 1,
      f"实际: {len(results)}")

# 直接用 run 调用（传入不足数据，验证框架层错误处理）
r = orch.run("bazi_analysis", plate_dict={"test": True})
check("run 返回 CapabilityResult（错误由框架捕获）", isinstance(r, CapabilityResult))


# ══════════════════════════════════════════════════════════
# 6. ensure_defaults 行为验证
# ══════════════════════════════════════════════════════════

print(f"\n{B}═══ 6. 生命周期 ═══{N}\n")

orch2 = AnalysisOrchestrator()
check("新实例未注册", not orch2._defaults_registered)

# 调用 summary 自动触发注册
orch2.summary()
check("summary() 触发自动注册", orch2._defaults_registered)

# 手动 router 注入
custom_router = IntentRouter(keywords={"custom": ["定制"]})
orch3 = AnalysisOrchestrator(router=custom_router)
check("注入自定义 router", orch3.router is custom_router)
check("自定义 router 可路由",
      orch3.router.resolve("定制分析") == "custom")


# ══════════════════════════════════════════════════════════
# 7. Tool 动态注入（Capability → Tool 关联）
# ══════════════════════════════════════════════════════════

print(f"\n{B}═══ 7. Tool 动态注入 ═══{N}\n")

# get_tools_for_capability
bazi_tools = orch.get_tools_for_capability("bazi_analysis")
check("bazi_analysis 关联 3 个 Tool",
      len(bazi_tools) == 3,
      f"实际: {bazi_tools}")
check("bazi_analysis 包含 paipan_bazi",
      "paipan_bazi" in bazi_tools)
check("bazi_analysis 包含 wuxing_query",
      "wuxing_query" in bazi_tools)
check("bazi_analysis 包含 kb_retrieve",
      "kb_retrieve" in bazi_tools)

ziwei_tools = orch.get_tools_for_capability("ziwei_analysis")
check("ziwei_analysis 关联 3 个 Tool",
      len(ziwei_tools) == 3,
      f"实际: {ziwei_tools}")
check("ziwei_analysis 包含 paipan_ziwei",
      "paipan_ziwei" in ziwei_tools)

verify_tools = orch.get_tools_for_capability("verify_panel")
check("verify_panel 关联 1 个 Tool",
      len(verify_tools) == 1,
      f"实际: {verify_tools}")
check("verify_panel = kb_retrieve",
      verify_tools == ["kb_retrieve"])

cross_tools = orch.get_tools_for_capability("cross_validate")
check("cross_validate 关联 5 个 Tool（全量）",
      len(cross_tools) == 5,
      f"实际: {cross_tools}")

# 不存在的 Capability
check("不存在的能力返回空列表",
      orch.get_tools_for_capability("nonexistent") == [])

# route() 注入工具验证（不调 LLM，仅验证参数传递）
result = orch.route("帮我排八字", inject_tools=True,
                    plate_dict={"input": {"birth_datetime": "2005-08-19 01:35", "gender": "男"}})
check("route 带 inject_tools 不崩溃", isinstance(result, CapabilityResult))

# inject_tools=False 验证
result_no_inject = orch.route("帮我排八字", inject_tools=False)
check("route inject_tools=False 不崩溃", isinstance(result_no_inject, CapabilityResult))


# ══════════════════════════════════════════════════════════
# 8. Function Calling 循环（结构测试，不调 LLM）
# ══════════════════════════════════════════════════════════

print(f"\n{B}═══ 8. Function Calling 循环 ═══{N}\n")

from services.orchestrator import FunctionCallingLoop

fc = FunctionCallingLoop(orch.tools, max_rounds=5)
check("FunctionCallingLoop 创建成功", isinstance(fc, FunctionCallingLoop))
check("max_rounds = 5", fc.max_rounds == 5)

# 测试 run_with_fc 参数校验（不真正调 LLM）
result = orch.run_with_fc(
    user_input="帮我排八字",
    system_prompt="测试",
    user_message="测试消息",
)
check("run_with_fc 不传 messages 用 user_message 构建",
      isinstance(result, dict))

result = orch.run_with_fc(
    capability_name="bazi_analysis",
    system_prompt="你是一个八字命理师",
    messages=[{"role": "user", "content": "排盘"}],
)
check("run_with_fc 指定 capability 跳过路由",
      isinstance(result, dict))

result = orch.run_with_fc(
    user_input="今天天气",
    system_prompt="测试",
    messages=[{"role": "user", "content": "测试"}],
)
check("run_with_fc 无关输入返回失败",
      not result.get("success", True) and "无法匹配" in result.get("error", ""))

# 验证 Tool 动态注入逻辑
bazi_tools = orch.get_tools_for_capability("bazi_analysis")
check("bazi_analysis 的 Tool 有 3 个",
      len(bazi_tools) == 3,
      f"实际: {bazi_tools}")

# tool_names 匹配验证
check("bazi_analysis Tool 包含 paipan_bazi",
      "paipan_bazi" in bazi_tools)
check("bazi_analysis Tool 包含 kb_retrieve",
      "kb_retrieve" in bazi_tools)


# ══════════════════════════════════════════════════════════
# 结果
# ══════════════════════════════════════════════════════════

print(f"\n{B}═══ 结果 ═══{N}")
print(f"  通过: {G}{pass_count}{N}  /  失败: {R}{fail_count}{N}  /  总计: {B}{total}{N}")
if fail_count == 0:
    print(f"\n  {G}🎉 编排层集成测试全部通过{N}")
else:
    print(f"\n  {R}💥 有 {fail_count} 项测试失败{N}")

sys.exit(0 if fail_count == 0 else 1)
