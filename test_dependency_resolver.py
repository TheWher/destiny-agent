#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""依赖解析纯函数测试 — Kahn 拓扑排序 + 环检测 + 版本比对

Phase 2 依赖解析的纯函数层。测试不依赖 PluginManager，
输入输出都是纯数据，测完就是最终形态。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.dependency_resolver import (
    DepRequirement, resolve_dependencies, parse_semver,
)

G = '\033[92m'; R = '\033[91m'; Y = '\033[93m'; N = '\033[0m'; B = '\033[1m'
pass_count = 0; fail_count = 0; total = 0

def check(name, condition, detail=''):
    global pass_count, fail_count, total
    total += 1
    if condition:
        pass_count += 1; print(f'{G}✅{N} [{name}] {detail}')
    else:
        fail_count += 1; print(f'{R}❌{N} [{name}] {detail}')


def D(name, constraint=""):
    """便捷构造 DepRequirement"""
    return DepRequirement(name=name, constraint=constraint)


# ══════════════════════════════════════════════════════════
# 1. 拓扑排序
# ══════════════════════════════════════════════════════════

def test_topological_order():
    print(f"\n{B}═══ 1. 拓扑排序 ═══{N}\n")

    # ── 1.1 无依赖的简单图 ──
    res = resolve_dependencies({"a": [], "b": [], "c": []})
    check("无依赖-ok", res.ok)
    check("无依赖-全排入", len(res.order) == 3, f"order={res.order}")

    # ── 1.2 链式依赖 a→b→c：c 必须先于 b，b 先于 a ──
    res = resolve_dependencies({
        "a": [D("b")],
        "b": [D("c")],
        "c": [],
    })
    check("链式-ok", res.ok)
    order = list(res.order)
    check("链式-c 先于 b", order.index("c") < order.index("b"), f"order={order}")
    check("链式-b 先于 a", order.index("b") < order.index("a"))

    # ── 1.3 菱形依赖 a→(b,c)→d ──
    res = resolve_dependencies({
        "a": [D("b"), D("c")],
        "b": [D("d")],
        "c": [D("d")],
        "d": [],
    })
    check("菱形-ok", res.ok)
    order = list(res.order)
    check("菱形-d 最先", order[0] == "d", f"order={order}")
    check("菱形-b 先于 a", order.index("b") < order.index("a"))
    check("菱形-c 先于 a", order.index("c") < order.index("a"))

    # ── 1.4 自依赖 a→a ──
    res = resolve_dependencies({"a": [D("a")]})
    check("自依赖-不ok", not res.ok)
    check("自依赖-环检测", "a" in res.cycle, f"cycle={res.cycle}")
    check("自依赖-错误信息人类可读", "循环依赖" in res.errors[0], res.errors[0])

    # ── 1.5 两节点互依赖 a→b, b→a ──
    res = resolve_dependencies({"a": [D("b")], "b": [D("a")]})
    check("互依赖-不ok", not res.ok)
    check("互依赖-环含两节点", set(res.cycle) == {"a", "b"}, f"cycle={res.cycle}")
    check("互依赖-错误列出环", "→" in res.errors[0], res.errors[0])

    # ── 1.6 混合：一部分有环一部分无环 ──
    res = resolve_dependencies({
        "x": [],
        "y": [D("x")],
        "p": [D("q")],
        "q": [D("p")],
    })
    check("混合-不ok", not res.ok)
    check("混合-环定位到 pq", set(res.cycle) == {"p", "q"}, f"cycle={res.cycle}")

    # ── 1.7 缺失依赖（有版本表时检测生效）──
    res = resolve_dependencies(
        {"a": [D("ghost")]},
        available_versions={"a": "1.0.0"},  # 版本表内无 ghost
    )
    check("缺失依赖-不ok", not res.ok)
    check("缺失依赖-错误含插件名", "ghost" in res.errors[0], res.errors[0])
    check("缺失依赖-错误含依赖方", "a" in res.errors[0])


# ══════════════════════════════════════════════════════════
# 2. 版本比对
# ══════════════════════════════════════════════════════════

def test_version_check():
    print(f"\n{B}═══ 2. 版本比对 ═══{N}\n")

    versions = {"lib": "1.2.0", "core": "2.0.0", "alpha": "1.0.0-alpha.1"}

    # ── 2.1 满足约束 ──
    res = resolve_dependencies(
        {"app": [D("lib", ">=1.0.0"), D("core", ">=2.0.0")]},
        available_versions=versions,
    )
    check(">= 满足", res.ok, f"errors={res.errors}")

    # ── 2.2 不满足约束 ──
    res = resolve_dependencies(
        {"app": [D("lib", ">=2.0.0")]},
        available_versions=versions,
    )
    check(">= 不满足-不ok", not res.ok)
    check(">= 不满足-错误可读", "1.2.0" in res.errors[0] and ">=2.0.0" in res.errors[0],
          res.errors[0])

    # ── 2.3 == 精确匹配 ──
    res = resolve_dependencies(
        {"app": [D("lib", "==1.2.0")]},
        available_versions=versions,
    )
    check("== 精确匹配", res.ok)
    res = resolve_dependencies(
        {"app": [D("lib", "1.2.0")]},  # 裸版本号视为 ==
        available_versions=versions,
    )
    check("裸版本号视为==", res.ok)

    # ── 2.4 非法约束 / 非法版本 ──
    res = resolve_dependencies(
        {"app": [D("lib", "banana")]},
        available_versions=versions,
    )
    check("非法约束-不ok", not res.ok)
    check("非法约束-错误可读", "banana" in res.errors[0], res.errors[0])

    # ── 2.5 不传 available_versions：跳过版本比对，但图外依赖仍报缺失 ──
    res = resolve_dependencies({"app": [D("lib", ">=999.0.0")]})
    check("无版本表-跳过版本比对", not res.ok)  # 不报版本错，但 lib 是图外依赖
    check("无版本表-报缺失而非版本",
          "不存在" in res.errors[0] and "不满足" not in res.errors[0],
          res.errors[0])

    # ── 2.6 prerelease 版本比对 ──
    res = resolve_dependencies(
        {"app": [D("alpha", ">=1.0.0")]},
        available_versions=versions,
    )
    check("prerelease 版本可比对", res.ok, f"errors={res.errors}")


# ══════════════════════════════════════════════════════════
# 3. SemVer 解析
# ══════════════════════════════════════════════════════════

def test_semver():
    print(f"\n{B}═══ 3. SemVer 解析 ═══{N}\n")

    valid = [("1.0.0", (1, 0, 0)), ("10.20.30", (10, 20, 30)),
             ("1.0.0-alpha", (1, 0, 0)), ("1.0.0+build", (1, 0, 0))]
    for v, expected in valid:
        got = parse_semver(v)
        check(f"合法({v})", got == expected, f"got={got}")

    invalid = ["1.0", "one.two.three", "v1.0.0", "", "latest", None]
    for v in invalid:
        check(f"非法({repr(v)})", parse_semver(v) is None)


# ══════════════════════════════════════════════════════════
# 4. 输入健壮性
# ══════════════════════════════════════════════════════════

def test_robustness():
    print(f"\n{B}═══ 4. 输入健壮性 ═══{N}\n")

    # ── 4.1 空图 ──
    res = resolve_dependencies({})
    check("空图-ok", res.ok)
    check("空图-空序", res.order == ())

    # ── 4.2 依赖声明不是列表 ──
    res = resolve_dependencies({"a": "not_a_list"})
    check("非法依赖类型-不ok", not res.ok)
    check("非法依赖类型-错误可读", "列表" in res.errors[0], res.errors[0])

    # ── 4.3 依赖项是纯字符串（兼容简写）──
    res = resolve_dependencies({"a": ["b"], "b": []})
    check("字符串简写-ok", res.ok)
    check("字符串简写-b 先于 a", list(res.order).index("b") < list(res.order).index("a"))

    # ── 4.4 重复依赖去重 ──
    res = resolve_dependencies({"a": [D("b"), D("b")], "b": []})
    check("重复依赖-不报错", res.ok)


# ── 主入口 ─────────────────────────────────────────────

if __name__ == "__main__":
    print(f"\n{B}{'='*60}{N}")
    print(f"{B}  依赖解析纯函数测试  Phase 2{N}")
    print(f"{B}{'='*60}{N}")

    test_topological_order()
    test_version_check()
    test_semver()
    test_robustness()

    print(f"\n\n{B}{'='*60}{N}")
    print(f"{B}  测试汇总{N}")
    print(f"{B}{'='*60}{N}")
    print(f"  {G}通过: {pass_count}{N}  {R}失败: {fail_count}{N}  总计: {total}")

    if fail_count == 0:
        print(f"\n  {G}{B}✅ 依赖解析纯函数全过{N}")
    else:
        print(f"\n  {R}{B}❌ 有 {fail_count} 项失败{N}")

    sys.exit(0 if fail_count == 0 else 1)
