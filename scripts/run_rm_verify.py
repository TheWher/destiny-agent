# -*- coding: utf-8 -*-
"""日照雷门/月朗天门构造盘 LLM 验证（最后一步，¥0.05 级，King 已批）。
走生产路径：ziwei_paipan → plate_to_dict → analyze_ziwei（含格局注入+词典）。"""
import json, os, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from ziwei_calculator import ziwei_paipan, plate_to_dict
from services.ziwei_analysis import analyze_ziwei

CASES = [
    ("日照雷门", [1941, 1, 10, 20, 0, "男"]),
    ("月朗天门", [1941, 1, 10, 4, 0, "男"]),
]
OUT = os.path.join(ROOT, "docs", "geju_rm_verify_v1.json")

results = []
for name, birth in CASES:
    plate = ziwei_paipan(*birth)
    pd = plate_to_dict(plate, {
        "birth_datetime": f"{birth[0]}-{birth[1]:02d}-{birth[2]:02d} {birth[3]:02d}:00",
        "gender": birth[5],
    })
    t0 = time.time()
    r = analyze_ziwei(pd, timeout=300)
    dt = round(time.time() - t0, 1)
    rec = {"geju": name, "birth": birth, "elapsed_s": dt}
    if not r.get("success"):
        rec["ok"] = False
        rec["error"] = r.get("error")
    else:
        rec["ok"] = True
        rec["text"] = r.get("analysis", "")
        rec["model"] = r.get("model")
        rec["usage"] = r.get("usage", {})
    results.append(rec)
    print(f"== {name} ok={rec['ok']} {dt}s ==")
    if rec["ok"]:
        print(rec["text"][:600])
    print("---")

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print("saved:", OUT)
