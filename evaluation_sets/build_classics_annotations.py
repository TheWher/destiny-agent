#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生成 ziwei_classics_annotations.json 骨架。

结构（韩湘生定案）：
  {格局名: {quotes: [{text, source|null}], note: str|null, source_truth: "原文|混合|转述"}}

规则：
- 引文句判别式：引号内容能独立成完整论断（有主谓的文言陈述）→ quotes；名词性质（格名/星名/术语）→ 留 note
- 14 条原文：整段引文进 quotes（source 从原标出处取），note=引文后的按语
- 3 条混合：逐段按判别式拆（杀破狼格 2 引文、府相朝垣 2 引文、三奇嘉会 2 引文；紫微独坐/巨日同宫按内容判定）
- 23 条转述：quotes=[]，note=整条内容，source_truth=转述
"""
import json
import pathlib

BASE = pathlib.Path(__file__).resolve().parent.parent / "knowledge_base"
OUT = pathlib.Path(__file__).resolve().parent.parent / "knowledge_base" / "ziwei_classics_annotations.json"

with open(BASE / "ziwei_classics.json", encoding="utf-8") as f:
    cj = json.load(f)
patterns = cj["patterns"]

annotations = {}

# ═══ 原文 14 条：引文带出处，note=按语 ═══
yuanwen = {
    "紫府同宫": (["紫府同宫，终身福厚。"], "全书", "天府紫微同守命宫，三方辅弼昌曲拱照，必主富贵。"),
    "君臣庆会": (["紫微居垣，遇左辅右弼文昌文曲天魁天钺，君臣庆会，才擅经邦。"], "全书", "帝王得贤臣辅佐之象。"),
    "日月并明": (["日月并明，佐九重于尧殿。"], "骨髓赋", "太阳太阴同守命宫，阴阳调和。"),
    "月朗天门": (["月朗天门，进爵封侯。"], "骨髓赋", "太阴在亥宫为庙旺之地。亥为天门，太阴居之，情感丰富，文艺天赋。"),
    "日照雷门": (["日照雷门，荣华富贵。"], "骨髓赋", "太阳在卯宫为初升之象，朝气蓬勃，光明磊落。"),
    "机月同梁格": (["机月同梁，作吏人。"], "全书", "天机太阴天同天梁四星汇聚，宜文职公务员。"),
    "火贪格": (["贪铃并守，将相之名。"], "骨髓赋", "贪狼遇火星或铃星同宫会照，爆发力强，横发之格。"),
    "铃贪格": (["贪铃并守，将相之名。"], "骨髓赋", "贪狼遇铃星，晚发之格，厚积薄发。"),
    "禄马交驰": (["天禄天马，惊人甲第。"], "骨髓赋", "禄存天马同宫，奔波中得财，名利双收。"),
    "命宫化权": (["出世荣华，权禄守财官之位。"], "骨髓赋", "化权在命宫，掌控力强。"),
    "火铃夹命": (["火星铃星专作祸。"], "骨髓赋", "火铃分居命宫前后夹命，性急冲动，需防突发意外。"),
    "辅弼夹命": (["夹贵夹禄少人知，夹权夹科世所宜。"], "骨髓赋", "左辅右弼夹命，贵人运极强。"),
}

for name, (quotes, src, note) in yuanwen.items():
    annotations[name] = {
        "quotes": [{"text": q, "source": src} for q in quotes],
        "note": note,
        "source_truth": "原文",
    }

# ═══ 混合 3+2 条：逐段拆 ═══
hunyhe = {
    "紫微独坐": {  # 混合：《全书》原文整句为引文（完整文言论断），note 为按语
        "quotes": [{"text": "紫微独坐命宫，无辅弼为孤君，有辅弼朝拱则成「百官朝拱」格。", "source": "全书"}],
        "note": "紫微独坐命宫，无辅弼为孤君，有辅弼朝拱则成百官朝拱格。",
        "source_truth": "混合",
    },
    "巨日同宫": {  # 《全书》转述 + 「巨日同宫，官封三代」是引文句；note 纯白话去书名号
        "quotes": [{"text": "巨日同宫，官封三代", "source": "全书"}],
        "note": "太阳巨门同宫在命，口才出众。",
        "source_truth": "混合",
    },
    "杀破狼格": {  # 《全书》转述 + 骨髓赋两引文；note 纯白话去书名号
        "quotes": [
            {"text": "七杀破军宜出外", "source": "骨髓赋"},
            {"text": "七杀朝斗，爵禄荣昌", "source": "骨髓赋"},
        ],
        "note": "七杀破军贪狼皆为动星。三者齐聚，大起大落，变动中求发展。",
        "source_truth": "混合",
    },
    "府相朝垣": {  # 骨髓赋两引文
        "quotes": [
            {"text": "天府天相乃为衣禄之神，为仕为官，定主亨通之兆", "source": "骨髓赋"},
            {"text": "府相朝垣，食禄万钟", "source": "骨髓赋"},
        ],
        "note": "天府天相分守命三方四正。",
        "source_truth": "原文",
    },
    "三奇嘉会": {  # 骨髓赋两引文
        "quotes": [
            {"text": "科权禄拱，名誉昭彰", "source": "骨髓赋"},
            {"text": "科权对拱，跃三汲于禹门", "source": "骨髓赋"},
        ],
        "note": "化禄化权化科会于三方四正，富贵双全。",
        "source_truth": "原文",
    },
}
for name, data in hunyhe.items():
    annotations[name] = data

# ═══ 转述 23 条：quotes=[], note=原内容，去书名号前缀 ═══
zhuanshu_keys = [
    "紫微天相", "紫微破军", "紫微七杀", "紫微贪狼",
    "命宫化禄", "命宫化忌", "财帛化禄", "命无正曜",
    "昌曲夹命", "魁钺夹命",
    "廉贞", "天机", "太阳", "武曲", "天同", "天府", "太阴", "贪狼", "巨门", "天相", "天梁", "七杀", "破军",
]
for name in zhuanshu_keys:
    raw = patterns[name]
    # 去掉《XX》前缀（书名号挂着转述，不能当出处呈现）
    note = raw.split("》", 1)[-1].strip() if "》" in raw else raw
    annotations[name] = {
        "quotes": [],
        "note": note,
        "source_truth": "转述",
    }

# ═══ 校验：40 条全覆盖 + note 纯净（呈现只看 quotes，note 必须无书名号/引号） ═══
missing = [k for k in patterns if k not in annotations]
extra = [k for k in annotations if k not in patterns]
assert not missing, f"missing: {missing}"
assert not extra, f"extra: {extra}"
assert len(annotations) == 40, len(annotations)

# note 纯净性终检：任何条目的 note 不得含《》或「」，否则假出处会漏进 prompt
for k, a in annotations.items():
    note = a["note"] or ""
    for bad in ["《", "》", "「", "」"]:
        assert bad not in note, f"note 含 {bad}: {k} -> {note}"

# source_truth 分布
from collections import Counter
print("source_truth 分布:", Counter(a["source_truth"] for a in annotations.values()))
print("quotes 为空条数:", sum(1 for a in annotations.values() if not a["quotes"]))

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(annotations, f, ensure_ascii=False, indent=2)
print(f"written: {OUT}")
