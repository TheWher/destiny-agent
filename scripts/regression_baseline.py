# -*- coding: utf-8 -*-
"""
regression_baseline.py — 手动工具轨直跑基线（2026-08-05 晚立）

背景：TODO-PAIPAN-PYTEST 参数化前先落"行为保持参照"。今天报过的 58/29/19 全是对话账，
首次直跑落文件才是数字第一次上机器账。退出码 + 计数 + 时间戳进 json，参数化后 diff。

用法：python scripts/regression_baseline.py
输出：evaluation_reports/regression_baseline_{YYYYMMDD_HHMMSS}.json
"""
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 手动轨脚本（八本账 + check_ganzhi）：(相对路径, 描述)
SCRIPTS = [
    ("test_paipan.py", "排盘 TEST_CASES 29 条（main 直跑）"),
    ("test_ziwei.py", "紫微全量 58 用例（main 直跑，含日月并明组）"),
    ("scripts/verify_laiyin_anchors.py", "来因宫双锚校验尺（旗舰，main 直跑）"),
    ("scripts/verify_geju_mingzhu.py", "日月系格局断言 19 条（main 直跑）"),
    ("scripts/check_ganzhi.py", "干支机检（CLAUDE.md 机检清单）"),
    ("scripts/verify_palace_fix.py", "六雷修复验收（模块级直接执行）"),
    ("test_orchestrator.py", "orchestrator 测试（模块级 sys.exit）"),
    ("test_e2e_fc.py", "e2e 测试（__main__ 守卫包 sys.exit(main())）"),
    ("scripts/test_pw.py", "密码调试脚本（顶 test_ 前缀，import app 副作用）"),
]


def parse_count(text):
    """宽松解析计数：'X 通过' / 'ALL PASS' / '全部通过'。解析失败不致命，退出码为准。"""
    m = re.search(r"(\d+)\s*通过", text)
    if m:
        return int(m.group(1))
    if "ALL PASS" in text or "全部通过" in text:
        return "pass"
    return None


def run_one(rel, desc):
    path = os.path.join(ROOT, rel)
    t0 = time.time()
    rec = {"script": rel, "desc": desc, "ts": datetime.now().isoformat(timespec="seconds")}
    try:
        proc = subprocess.run(
            [sys.executable, path],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=120,
        )
        rec["exit_code"] = proc.returncode
        rec["elapsed_s"] = round(time.time() - t0, 2)
        tail = (proc.stdout or "")[-600:]
        rec["count"] = parse_count(proc.stdout or "")
        rec["stdout_tail"] = tail
        if proc.stderr and proc.stderr.strip():
            rec["stderr_tail"] = proc.stderr[-300:]
    except subprocess.TimeoutExpired:
        rec["exit_code"] = None
        rec["elapsed_s"] = round(time.time() - t0, 2)
        rec["count"] = None
        rec["stdout_tail"] = "TIMEOUT(120s)"
    except Exception as e:  # noqa: BLE001
        rec["exit_code"] = "ERR"
        rec["elapsed_s"] = round(time.time() - t0, 2)
        rec["stdout_tail"] = f"EXC: {e}"
    return rec


def main():
    results = []
    for rel, desc in SCRIPTS:
        print(f"== {rel} ({desc})", flush=True)
        rec = run_one(rel, desc)
        print(f"   exit={rec['exit_code']} count={rec['count']} {rec['elapsed_s']}s", flush=True)
        results.append(rec)

    payload = {
        "kind": "manual-track regression baseline",
        "created": datetime.now().isoformat(timespec="seconds"),
        "note": "TODO-PAIPAN-PYTEST 参数化前的行为保持参照；pytest 轨可见性另走逐本 --collect-only",
        "scripts": results,
    }
    out_dir = os.path.join(ROOT, "evaluation_reports")
    os.makedirs(out_dir, exist_ok=True)
    fname = "regression_baseline_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".json"
    out_path = os.path.join(out_dir, fname)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print()
    print("基线已落:", out_path)


if __name__ == "__main__":
    main()
