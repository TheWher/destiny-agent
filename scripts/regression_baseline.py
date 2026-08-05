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

# 手动轨脚本（工具轨八本 + check_ganzhi）：(相对路径, 描述, timeout秒)
# timeout 单独标状态（timeout ≠ pass ≠ fail，不混进 exit 码）
# 2026-08-06 判类落地：verify_palace_fix 退役归档（一次性验收，唯一机器断言金表已并入 test_ziwei）；
# e2e_fc 从工具轨单列 requires-llm（真实 LLM E2E，基线 timeout 天生不稳，见 REQUIRES_LLM）
SCRIPTS = [
    ("test_paipan.py", "排盘 TEST_CASES 29 条（main 直跑）", 60),
    ("test_ziwei.py", "紫微全量 59 用例（main 直跑，含日月并明组+十二宫功能名金表组）", 60),
    ("scripts/verify_laiyin_anchors.py", "来因宫双锚校验尺（旗舰，main 直跑）", 60),
    ("scripts/verify_geju_mingzhu.py", "日月系格局断言 19 条（main 直跑）", 60),
    ("scripts/check_ganzhi.py", "干支机检（CLAUDE.md 机检清单）", 60),
    ("test_orchestrator.py", "orchestrator 测试（手动轨 _run_all，pytest 轨 4 error-path）", 60),
    ("scripts/smoke_password.py", "密码冒烟脚本（原 test_pw.py 改名，不再顶 test_ 前缀；直跑 ModuleNotFoundError 已知，判类补真测试待定）", 30),
]

# requires-llm 轨（2026-08-06 判类：真实 LLM 端到端冒烟，需 API key，
# run_with_fc 120s×8轮×4用例最坏 64 分钟，基线 timeout 天生不稳，不参与工具轨判定）
REQUIRES_LLM = [
    ("test_e2e_fc.py", "端到端 Function Calling（真实 LLM；结构评估纯函数待拆 pytest+mock 测）", 30),
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
        "note": "参数化后的行为保持参照；pytest 轨全量 108 另见 pytest 直跑；e2e_fc 从工具轨单列 requires-llm（真实 LLM E2E，基线 timeout 天生不稳）",
        "scripts": results,
        "requires_llm": [
            {"script": rel, "desc": desc,
             "status": "requires-llm",
             "note": "2026-08-06 判类：真实 LLM 端到端冒烟，需 API key；结构评估纯函数 evaluate_tool_sequence/evaluate_text_quality 待拆 pytest+mock"}
            for rel, desc, _t in REQUIRES_LLM
        ],
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
