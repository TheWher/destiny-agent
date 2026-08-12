# -*- coding: utf-8 -*-
import sys, re
sys.stdout.reconfigure(encoding="utf-8")

for tag, p in {
    "mingtu": "tmp_sdzj0170/datalayer_md/sd_sdzj0170_mingtu.md",
    "v5": "tmp_sdzj0170/datalayer_md/sd_sdzj0170_v5.md",
    "v2": "tmp_sdzj0170/datalayer_md/sd_sdzj0170_v2.md",
}.items():
    t = open(p, encoding="utf-8").read()
    print("===", tag, "===")
    for pat in ["藏凶", "藏㐫", "逢沖破", "逢冲破", "逢衝破"]:
        n = t.count(pat)
        if n:
            for m in list(re.finditer(pat, t))[:2]:
                s = max(0, m.start()-30); e = min(len(t), m.end()+30)
                print(f"  {pat}: ...{t[s:e].strip()}...")
