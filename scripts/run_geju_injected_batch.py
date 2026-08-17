# -*- coding: utf-8 -*-
"""注入后批量跑构造盘：生产路径 _build_ziwei_user_message（含格局注入）→ analyze_ziwei 出 LLM 原文。
输入：docs/geju_expected_cases_v1.json（baseline 清单，取 birth/id/expected）
输出：docs/geju_injected_cases_v1.json（同结构，text=注入后 LLM 原文，另存 usage/model/elapsed）
断点续跑：已存在的 id 跳过。失败重试一次。
成本管控：全量约 30-40 分钟，deepseek-v4-flash 粗估 ¥1-3（预算线 4 元内）。
2026-08-17 扩展：--src/--dst 可选（多清单追加跑，如 v2_nm 追加进同一输出）。"""
import argparse
import json, os, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

SRC = os.path.join(ROOT, "docs", "geju_expected_cases_v1.json")
DST = os.path.join(ROOT, "docs", "geju_injected_cases_v1.json")

from ziwei_calculator import ziwei_paipan, plate_to_dict
from services.ziwei_analysis import analyze_ziwei


def run_one(case: dict) -> dict:
    birth = case["birth"]
    plate = ziwei_paipan(*birth)
    pd = plate_to_dict(plate, {
        "birth_datetime": f"{birth[0]}-{birth[1]:02d}-{birth[2]:02d} {birth[3]:02d}:00",
        "gender": birth[5],
    })
    t0 = time.time()
    r = analyze_ziwei(pd, timeout=300)
    dt = round(time.time() - t0, 1)
    if not r.get("success"):
        return {"id": case["id"], "ok": False, "error": r.get("error"), "elapsed": dt}
    return {
        "id": case["id"], "ok": True, "text": r.get("analysis", ""),
        "model": r.get("model"), "usage": r.get("usage", {}), "elapsed": dt,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', default=SRC, help='expected 清单 JSON 路径')
    ap.add_argument('--dst', default=DST, help='注入后输出 JSON 路径')
    args = ap.parse_args()
    src = args.src
    dst = args.dst
    with open(src, encoding="utf-8") as f:
        data = json.load(f)
    cases = data["cases"]

    out = {"meta": {**data["meta"], "note": data["meta"]["note"] + "（text=注入后 LLM 原文，2026-08-17 主路径格局注入补齐后生产路径实跑）"},
           "cases": []}
    if os.path.exists(dst):
        with open(dst, encoding="utf-8") as f:
            prev = json.load(f)
        done = {c["id"] for c in prev.get("cases", [])}
        out["cases"] = prev["cases"]
    else:
        done = set()

    todo = [c for c in cases if c["id"] not in done]
    print(f"src={os.path.basename(src)} dst={os.path.basename(dst)} total={len(cases)} done={len(done)} todo={len(todo)}")
    order = {c["id"]: i for i, c in enumerate(cases)}
    for i, case in enumerate(todo, 1):
        r = run_one(case)
        if not r["ok"]:
            time.sleep(2)
            r = run_one(case)  # 重试一次
        rec = {"id": case["id"], "kind": case["kind"], "birth": case["birth"],
               "expected": case["expected"]}
        if r["ok"]:
            rec["text"] = r["text"]
            rec["meta_run"] = {"model": r["model"], "usage": r["usage"], "elapsed_s": r["elapsed"]}
        else:
            rec["error"] = r["error"]
        out["cases"] = [c for c in out["cases"] if c["id"] != case["id"]]
        out["cases"].append(rec)
        out["cases"].sort(key=lambda c: order.get(c["id"], 10 ** 9))
        with open(dst, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"[{i}/{len(todo)}] {case['id']} ok={r['ok']} {r.get('elapsed')}s "
              f"tok={r.get('usage', {}).get('input_tokens', 0)}+{r.get('usage', {}).get('output_tokens', 0)}")
    print("done.")


if __name__ == "__main__":
    main()
