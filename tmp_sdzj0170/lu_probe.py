# -*- coding: utf-8 -*-
import sys, re
sys.stdout.reconfigure(encoding="utf-8")

def norm(t):
    return re.sub(r"[\s，。、；：？！「」『』（）()\"'\u3000]", "", t)

files = {
    "v1": "tmp_sdzj0170/datalayer_md/sd_sdzj0170_v1.md",
    "all": "tmp_sdzj0170/datalayer_md/sd_sdzj0170_all.md",
    "刻本": "tmp_sdzj0170/shuge_ocr/fulltext_p1_528.txt",
}
for tag, p in files.items():
    t = norm(open(p, encoding="utf-8").read())
    print("===", tag, "长度", len(t))
    for ch in ["卤", "㐫", "凶", "禍", "祸"]:
        print(f"  {ch}: {t.count(ch)}")
    # 卤 的上下文
    for m in list(re.finditer("卤", t))[:3]:
        s = max(0, m.start()-20); e = min(len(t), m.end()+20)
        print(f"  卤位: ...{t[s:e]}...")
