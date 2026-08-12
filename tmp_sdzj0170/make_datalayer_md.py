# -*- coding: utf-8 -*-
import json, os, glob
OUT = r"D:\OH-WorkSpace\Destiny_agent\tmp_sdzj0170\full"
DATA = r"D:\OH-WorkSpace\Destiny_agent\tmp_sdzj0170\datalayer_md"
os.makedirs(DATA, exist_ok=True)
vols = ["v1","v2","v3","v4","v5","v7","mingtu"]
for v in vols:
    fn = os.path.join(OUT, f"{v}_zhujie_extract.json")
    if not os.path.exists(fn): continue
    d = json.load(open(fn, encoding="utf-8"))
    lines = []
    for kind, items in (("赋文", d["fuwen"]), ("注文", d["zhuwen"]), ("篇名", d["pianming"])):
        for it in items:
            lines.append(it)
    out = os.path.join(DATA, f"sd_sdzj0170_{v}.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(v, len(lines), "lines ->", out)
