# -*- coding: utf-8 -*-
import sys, re
sys.stdout.reconfigure(encoding="utf-8")

def norm(t):
    return re.sub(r"[\s，。、；：？！「」『』（）()\"'\u3000]", "", t)

files = {
    "v1": "tmp_sdzj0170/datalayer_md/sd_sdzj0170_v1.md",
    "v2": "tmp_sdzj0170/datalayer_md/sd_sdzj0170_v2.md",
    "juan1": "knowledge_base/obsidian/素材池/网页快照/2026-08-12-sdzj0170-juan1.md",
    "刻本全文": "tmp_sdzj0170/shuge_ocr/fulltext_p1_528.txt",
}
names = ["太微賦","太微赋","斗數準繩","斗数準绳","斗數准繩","斗数准绳",
         "斗數發微論","斗数发微论","骨髓賦","骨髓赋"]
for tag, p in files.items():
    t = norm(open(p, encoding="utf-8").read())
    hits = {n: t.count(n) for n in names if t.count(n) > 0}
    print(tag, hits)
