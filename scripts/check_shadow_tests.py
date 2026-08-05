# -*- coding: utf-8 -*-
"""
check_shadow_tests.py — 共享探针：捉影子（2026-08-06 韩湘生落）

背景：2026-08-05 晚双教训。e2e_fc 485 行 __main__ 守卫误报（探针只检单引号变体），
test_pw.py 顶 test_ 前缀装死（pytest 收集即 import app 副作用）。韩湘生引号修复 + mose
检测模式（module-level 执行 / test_ 前缀伪装）并成一把，落地 scripts/ 单一入口。

检出四类影子（test_*.py 与 scripts/*.py）：
  [collect-crash]  test_ 前缀且无 __main__ 守卫，模块级 sys.exit/副作用调用 → pytest 收集崩点
  [import-runs]    test_ 前缀且模块级副作用调用（import 即跑），有守卫但守卫外仍执行
  [zero-collect]   test_ 前缀但无任何 test_* 函数（pytest 零收集，静默零轨）
  [masquerade]     scripts/ 下 test_ 前缀文件（伪装测试，旧 test_pw.py 即此类）

守卫检测覆盖单双引号变体。纯 AST 判定模块级执行（naive 正则会把守卫内 sys.exit 也误报，
2026-08-06 韩湘生首跑核对时发现并修正）。

用法：python scripts/check_shadow_tests.py [--json]
退出码：0=无 collect-crash/import-runs/masquerade；1=有（可挂机检门槛）。
探针自身遵守本探针规则：__main__ 守卫 + 零模块级副作用（捉影子的脚本自己别成影子）。
"""
import ast
import json
import os
import re
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION = "1.0.0"

GUARD_RE = re.compile(r'if\s+__name__\s*==\s*["\']__main__["\']\s*:')

# 模块级可忽略的调用（样板代码，非副作用）
_BENIGN_ATTR = {
    ("sys", "path"): {"insert", "append"},
    ("sys", "stdout"): {"reconfigure"},
    ("sys", "stderr"): {"reconfigure"},
}
_BENIGN_NAMES = {"print"}


def _is_benign_call(c):
    """样板代码调用（非副作用）：print / sys.path.insert|append / sys.stdout|stderr.reconfigure"""
    if isinstance(c.func, ast.Attribute):
        # sys.path.insert / sys.path.append / sys.stdout.reconfigure
        if isinstance(c.func.value, ast.Attribute):
            root, mod = c.func.value.value, c.func.value.attr
            if isinstance(root, ast.Name) and root.id == "sys" and mod in ("path", "stdout", "stderr"):
                return c.func.attr in _BENIGN_ATTR.get(("sys", mod), set())
        return False
    if isinstance(c.func, ast.Name):
        return c.func.id in _BENIGN_NAMES
    return False


def _is_sys_exit(c):
    """sys.exit(x) / exit() / quit() 模块级调用"""
    if isinstance(c.func, ast.Attribute) and c.func.attr == "exit" \
            and isinstance(c.func.value, ast.Name) and c.func.value.id == "sys":
        return True
    return isinstance(c.func, ast.Name) and c.func.id in ("exit", "quit")


def scan_file(rel):
    """返回 (severity, kind, detail) 列表。severity: CRIT / WARN / INFO"""
    path = os.path.join(ROOT, rel)
    findings = []
    try:
        src = open(path, encoding="utf-8").read()
        tree = ast.parse(src)
    except Exception as e:  # noqa: BLE001
        return [("CRIT", "unparseable", f"解析失败: {e}")]
    name = os.path.basename(rel)
    is_test_prefix = name.startswith("test_")
    in_scripts = rel.replace("\\", "/").startswith("scripts/")
    has_guard = bool(GUARD_RE.search(src))
    test_fns = [n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]

    module_calls = [n.value for n in tree.body
                    if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)]
    module_exit = [c for c in module_calls if _is_sys_exit(c)]
    module_side = [c for c in module_calls if not _is_benign_call(c) and not _is_sys_exit(c)]

    if in_scripts and is_test_prefix:
        findings.append(("CRIT", "masquerade", "scripts/ 下 test_ 前缀伪装（pytest 可能收集即执行）"))

    if is_test_prefix:
        if module_exit and not has_guard:
            findings.append(("CRIT", "collect-crash", "模块级 sys.exit 且无 __main__ 守卫（pytest 收集崩点）"))
        elif module_exit:
            findings.append(("INFO", "module-exit", "模块级 sys.exit（守卫外）"))
        if module_side and not has_guard:
            findings.append(("CRIT", "import-runs", f"模块级副作用调用 {len(module_side)} 处且无守卫（import 即跑）"))
        elif module_side:
            findings.append(("WARN", "import-runs", f"守卫外模块级副作用调用 {len(module_side)} 处"))
        if not test_fns:
            findings.append(("WARN", "zero-collect", "无任何 test_* 函数（pytest 零收集，静默零轨）"))
        if not has_guard and not module_exit and not module_side:
            findings.append(("INFO", "no-guard", "无 __main__ 守卫（纯 pytest 文件可接受）"))

    return findings


def main():
    do_json = "--json" in sys.argv
    targets = []
    for f in sorted(os.listdir(ROOT)):
        if f.startswith("test_") and f.endswith(".py"):
            targets.append(f)
    scripts_dir = os.path.join(ROOT, "scripts")
    for f in sorted(os.listdir(scripts_dir)):
        if f.endswith(".py"):
            targets.append(os.path.join("scripts", f))

    rows = []
    n_crit = 0
    for rel in targets:
        for severity, kind, detail in scan_file(rel):
            if severity == "CRIT":
                n_crit += 1
            rows.append({"file": rel, "severity": severity, "kind": kind, "detail": detail})

    if do_json:
        payload = {
            "kind": "shared probe scan (shadow tests)",
            "probe_version": VERSION,
            "created": datetime.now().isoformat(timespec="seconds"),
            "scanned": len(targets),
            "crit_count": n_crit,
            "findings": rows,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"探针 v{VERSION} | 扫描 {len(targets)} 文件 | CRIT {n_crit}")
        for r in rows:
            print(f"  [{r['severity']}] {r['kind']} {r['file']} — {r['detail']}")
        if not rows:
            print("  无发现")

    sys.exit(1 if n_crit else 0)


if __name__ == "__main__":
    main()
