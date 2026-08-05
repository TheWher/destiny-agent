# -*- coding: utf-8 -*-
"""
regression_baseline.py — 手动工具轨直跑基线（2026-08-05 晚立）

背景：TODO-PAIPAN-PYTEST 参数化前先落"行为保持参照"。今天报过的 58/29/19 全是对话账，
首次直跑落文件才是数字第一次上机器账。退出码 + 计数 + 时间戳进 json，参数化后 diff。

用法：python scripts/regression_baseline.py
输出：docs/regression_baseline/regression_baseline_{YYYYMMDD_HHMMSS}.json（版本化锚点，入库；evaluation_reports/ 被 gitignore 不入库）
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

# 手动轨脚本（八本账 + check_ganzhi）：(相对路径, 描述, timeout秒)
# timeout 单独标状态（timeout ≠ pass ≠ fail，不混进 exit 码）；e2e_fc 已知直跑挂起（环境依赖），给短超时避免卡基线
SCRIPTS = [
    ("test_paipan.py", "排盘 TEST_CASES 29 条（main 直跑）", 60),
    ("test_ziwei.py", "紫微全量 58 用例（main 直跑，含日月并明组）", 60),
    ("scripts/verify_laiyin_anchors.py", "来因宫双锚校验尺（旗舰，main 直跑）", 60),
    ("scripts/verify_geju_mingzhu.py", "日月系格局断言 19 条（main 直跑）", 60),
    ("scripts/check_ganzhi.py", "干支机检（CLAUDE.md 机检清单）", 60),
    ("scripts/verify_palace_fix.py", "六雷修复验收（模块级直接执行）", 60),
    ("test_orchestrator.py", "orchestrator 测试（模块级 sys.exit）", 60),
    ("test_e2e_fc.py", "e2e 测试（__main__ 守卫包 sys.exit(main())，直跑挂起已知）", 30),
    ("scripts/test_pw.py", "密码调试脚本（顶 test_ 前缀，import app 副作用，直跑 ModuleNotFoundError 已知）", 30),
]


def parse_count(text):
    """宽松解析计数：'X 通过' / 'ALL PASS' / '全部通过'。解析失败不致命，退出码为准。"""
    m = re.search(r"(\d+)\s*通过", text)
    if m:
        return int(m.group(1))
    if "ALL PASS" in text or "全部通过" in text:
        return "pass"
    return None


def judge_status(exit_code, stderr, timeout):
    """状态判定（2026-08-05 hanako/mose 补）：
    clean = exit 0 且无 stderr 残留（手动轨绿色口径 = pytest 轨全绿同标准）；
    status: pass(干净绿) / warn(脏绿: exit0 但 stderr 残留) / fail(exit非0) / timeout / error。"""
    if exit_code is None:
        return "timeout", False
    if isinstance(exit_code, int):
        clean = (exit_code == 0) and (not stderr or not stderr.strip())
        if exit_code == 0 and clean:
            return "pass", True
        if exit_code == 0:
            return "warn", False
        return "fail", False
    return "error", False


def run_one(rel, desc, timeout):
    path = os.path.join(ROOT, rel)
    t0 = time.time()
    rec = {"script": rel, "desc": desc, "timeout_s": timeout, "ts": datetime.now().isoformat(timespec="seconds")}
    try:
        proc = subprocess.run(
            [sys.executable, path],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout,
        )
        rec["exit_code"] = proc.returncode
        rec["elapsed_s"] = round(time.time() - t0, 2)
        tail = (proc.stdout or "")[-600:]
        rec["count"] = parse_count(proc.stdout or "")
        rec["stdout_tail"] = tail
        if proc.stderr and proc.stderr.strip():
            rec["stderr_tail"] = proc.stderr[-300:]
        rec["status"], rec["clean"] = judge_status(proc.returncode, proc.stderr, timeout)
    except subprocess.TimeoutExpired:
        rec["exit_code"] = None
        rec["elapsed_s"] = round(time.time() - t0, 2)
        rec["count"] = None
        rec["stdout_tail"] = f"TIMEOUT({timeout}s)"
        rec["status"], rec["clean"] = "timeout", False
    except Exception as e:  # noqa: BLE001
        rec["exit_code"] = "ERR"
        rec["elapsed_s"] = round(time.time() - t0, 2)
        rec["stdout_tail"] = f"EXC: {e}"
        rec["status"], rec["clean"] = "error", False
    return rec


def main():
    results = []
    for rel, desc, timeout in SCRIPTS:
        print(f"== {rel} ({desc})", flush=True)
        rec = run_one(rel, desc, timeout)
        mark = "✅" if rec["clean"] else ("⏱" if rec["status"] == "timeout" else "⚠️")
        print(f"   [{rec['status']}] exit={rec['exit_code']} count={rec['count']} {rec['elapsed_s']}s {mark}", flush=True)
        results.append(rec)

    payload = {
        "kind": "manual-track regression baseline",
        "created": datetime.now().isoformat(timespec="seconds"),
        "note": "TODO-PAIPAN-PYTEST 参数化前的行为保持参照；pytest 轨可见性另走逐本 --collect-only",
        "scripts": results,
    }
    out_dir = os.path.join(ROOT, "docs", "regression_baseline")
    os.makedirs(out_dir, exist_ok=True)
    fname = "regression_baseline_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".json"
    out_path = os.path.join(out_dir, fname)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print()
    print("基线已落:", out_path)


if __name__ == "__main__":
    main()
