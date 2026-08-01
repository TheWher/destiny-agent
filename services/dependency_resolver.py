#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""依赖解析纯函数 — Kahn 拓扑排序 + 环检测 + 版本比对

Phase 2 落地。与 PluginManager 内部状态完全解耦：
- 输入：依赖图（纯数据）
- 输出：拓扑序或带环信息的错误对象

接 init_all 时只改调用方式，不改本模块签名。
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class DepRequirement:
    """一条依赖声明：插件名 + 版本约束（空串 = 任意版本）"""
    name: str
    constraint: str = ""


@dataclass
class ResolveResult:
    """依赖解析结果"""
    ok: bool
    order: tuple = ()                    # 拓扑序（依赖先于依赖方），ok=True 时有效
    cycle: tuple = ()                    # 环上的插件名序列（ok=False 且有环时有效）
    errors: list = field(default_factory=list)  # 人类可读错误信息
    failed_plugins: list = field(default_factory=list)  # 校验失败的插件名（供调用方定位 error 归属）


# ── SemVer 比对 ─────────────────────────────────────────

def parse_semver(version: str) -> Optional[tuple]:
    """解析 SemVer 为 (major, minor, patch)；非法返回 None"""
    if not version:
        return None
    core = version.split("+")[0].split("-")[0]
    parts = core.split(".")
    if len(parts) != 3:
        return None
    try:
        return (int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError:
        return None


def _parse_constraint(constraint: str) -> Optional[tuple]:
    """解析约束 '>=1.0.0' / '==1.2.0' / '>1.0' 等为 (op, semver)"""
    constraint = constraint.strip()
    for op in (">=", "<=", "==", ">", "<"):
        if constraint.startswith(op):
            ver = constraint[len(op):].strip()
            parsed = parse_semver(ver)
            if parsed is None:
                return None
            return (op, parsed)
    # 裸版本号，视为 ==
    parsed = parse_semver(constraint)
    if parsed is None:
        return None
    return ("==", parsed)


def _version_satisfies(version: tuple, op: str, target: tuple) -> bool:
    if op == ">=":
        return version >= target
    if op == "<=":
        return version <= target
    if op == ">":
        return version > target
    if op == "<":
        return version < target
    if op == "==":
        return version == target
    return False


# ── 主入口 ─────────────────────────────────────────────

def resolve_dependencies(
    dep_graph: dict,
    available_versions: Optional[dict] = None,
) -> ResolveResult:
    """解析依赖图，返回拓扑序或错误。

    Args:
        dep_graph: {plugin_name: list[DepRequirement]}，
                   每个插件声明的直接依赖（含版本约束）。
        available_versions: {plugin_name: version_str}，
                   已注册插件的版本号。用于比对约束；
                   未提供时跳过版本比对（只做拓扑序 + 环检测）。

    Returns:
        ResolveResult：
          ok=True  → order 为拓扑序（依赖先于依赖方）
          ok=False → errors 含人类可读错误；有环时 cycle 列出环上插件名
    """
    errors = []
    failed_plugins = []
    graph = {}          # name -> set(依赖名)
    # 存在性证据 = 图内节点 ∪ 版本表（版本表提供"已注册"证据）；
    # 图外依赖若没有任何证据 → 一律报缺失，无版本表不豁免
    all_names = set(dep_graph.keys())
    if available_versions is not None:
        all_names |= set(available_versions.keys())

    # 检查重复/非法输入
    for name, reqs in dep_graph.items():
        if not isinstance(reqs, (list, tuple)):
            errors.append(f"插件 '{name}' 的依赖声明必须是列表")
            continue
        req_names = set()
        for req in reqs:
            if isinstance(req, str):
                dep_name = req
                constraint = ""
            elif isinstance(req, DepRequirement):
                dep_name = req.name
                constraint = req.constraint
            else:
                errors.append(f"插件 '{name}' 的依赖项类型非法: {type(req).__name__}")
                continue
            req_names.add(dep_name)

            # 版本比对
            if available_versions and constraint:
                if dep_name not in available_versions:
                    continue  # 缺失依赖单独报，不在这里报版本
                actual = available_versions[dep_name]
                actual_v = parse_semver(actual)
                parsed_c = _parse_constraint(constraint)
                if actual_v is None:
                    errors.append(
                        f"依赖 '{dep_name}' 版本 '{actual}' 不是合法 SemVer"
                    )
                elif parsed_c is None:
                    errors.append(
                        f"依赖 '{dep_name}' 约束 '{constraint}' 无法解析"
                    )
                elif not _version_satisfies(actual_v, parsed_c[0], parsed_c[1]):
                    errors.append(
                        f"依赖 '{dep_name}' 版本 '{actual}' 不满足约束 '{constraint}'"
                    )
                    failed_plugins.append(name)

        graph[name] = req_names

    # 缺失依赖检测：图外依赖一律报缺失，版本表仅补充存在性证据
    for name, req_names in graph.items():
        for dep_name in req_names:
            if dep_name not in all_names:
                errors.append(
                    f"插件 '{name}' 依赖的 '{dep_name}' 不存在或未注册"
                )
                failed_plugins.append(name)

    if errors:
        return ResolveResult(ok=False, errors=errors,
                             failed_plugins=list(dict.fromkeys(failed_plugins)))

    # Kahn 拓扑排序
    # in_degree 只计"图内依赖"：依赖指向图外插件（版本表内已存在）时视为存量满足，
    # 不计入入度，否则本次 init 图中的节点会因外部依赖永远无法入队
    in_degree = {
        name: len({d for d in deps if d in graph})
        for name, deps in graph.items()
    }
    zero_queue = [name for name, deg in in_degree.items() if deg == 0]
    zero_queue.sort()  # 确定性：同名场景下按名字序
    order = []
    while zero_queue:
        name = zero_queue.pop(0)
        order.append(name)
        for other, deps in graph.items():
            if name in deps:
                in_degree[other] -= 1
                if in_degree[other] == 0:
                    zero_queue.append(other)
                    zero_queue.sort()

    if len(order) != len(graph):
        # 有环：从剩余节点 DFS 回溯出环
        remaining = [n for n in all_names if n not in order]
        cycle = _find_cycle(graph, remaining)
        return ResolveResult(
            ok=False,
            cycle=tuple(cycle),
            failed_plugins=list(cycle),
            errors=[
                f"检测到循环依赖: {' → '.join(cycle + [cycle[0]])}"
                if cycle else "检测到循环依赖（无法定位环）"
            ],
        )

    return ResolveResult(ok=True, order=tuple(order))


def _find_cycle(graph: dict, start_candidates: list) -> list:
    """从候选节点出发 DFS 找环，返回环上插件名序列（不含重复收尾）"""
    for start in start_candidates:
        path = []
        in_path = set()
        stack = [(start, iter(sorted(graph.get(start, set()))))]
        while stack:
            node, it = stack[-1]
            if node not in in_path:
                in_path.add(node)
                path.append(node)
            advanced = False
            for dep in it:
                if dep in in_path:
                    # 找到环：dep 是环的起点
                    idx = path.index(dep)
                    return path[idx:]
                if dep not in in_path:
                    stack.append((dep, iter(sorted(graph.get(dep, set())))))
                    advanced = True
                    break
            if not advanced:
                stack.pop()
                if path:
                    in_path.discard(path.pop())
    return []
