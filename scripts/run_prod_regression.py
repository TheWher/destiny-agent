#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生产档回归：embedding + 0.55 阈值下跑 dry-run + 阈值扫描。

动 knowledge_base 数据后必跑（阈值分界可能漂移）。用法：
    python scripts/run_prod_regression.py
预期：dry-run 87/87、文件级 0、平均 ~300B；阈值扫描 0.60 分界仍在（正 100%/负 100%）。
任一不满足 → 非零退出码，需检查数据变更是否吃掉了阈值余量。
"""
import os
import pathlib
import subprocess
import sys

PROJ = pathlib.Path(__file__).resolve().parent.parent
os.environ["KB_BACKEND"] = "embedding"
os.environ["KB_EMBEDDING_MODEL"] = os.environ.get(
    "KB_EMBEDDING_MODEL", str(PROJ / "models" / "bge-small-zh-v1.5"))
os.environ["KB_EMBEDDING_MIN_SCORE"] = "0.55"


def run(script: str):
    r = subprocess.run([sys.executable, script], cwd=PROJ, capture_output=True, text=True)
    return r


def main() -> int:
    print("=" * 60)
    print("生产档回归 1/2: dry-run（embedding + 0.55）")
    print("=" * 60)
    r1 = run("evaluation_sets/dry_run_check.py")
    out1 = (r1.stdout + r1.stderr)
    for line in out1.splitlines():
        if any(k in line for k in ("total=", "pass rate", "一致性", "文件级对", "平均返回长度")):
            print(line)
    ok1 = "passed=87" in out1 or ("failed=0" in out1 and "run=87" in out1)

    print()
    print("=" * 60)
    print("生产档回归 2/2: 阈值扫描（分界漂移检查）")
    print("=" * 60)
    r2 = run("evaluation_sets/threshold_eval.py")
    out2 = r2.stdout + r2.stderr
    for line in out2.splitlines():
        if "0.60" in line or "0.62" in line or "分界" in line:
            print(line)
    ok2 = "min_score=0.60" in out2 and "过滤 100%" in out2

    print()
    ok = ok1 and ok2
    print(f"回归结论: {'PASS' if ok else 'FAIL'}"
          f"（dry-run={'ok' if ok1 else 'FAIL'}，0.60 分界={'ok' if ok2 else 'FAIL'}）")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
