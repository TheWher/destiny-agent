#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""评测集 pair 扩池：从 KB 实际数据生成合法 target，产出 evaluation_sets/seed_pairs.json v0.2。

原则：
- target 全部来自 KB 实际存在的 key（用文件内既有用字，不新造）
- 白话问句 + 答案实时从 KB 取，字面不重叠（文言/引文段天然满足）
- keywords = 模拟命盘提取的检索词（新旧检索器共用同一组输入，数据同源）
- 三层归属：确定注入（fuzuo/classics）、工具可达（star_palace/hua）、计划扩展（classics_full）+ 直读表（tiaohou）
"""
import json
import pathlib

BASE = pathlib.Path(__file__).resolve().parent.parent / "knowledge_base"
OUT = pathlib.Path(__file__).resolve().parent / "seed_pairs.json"


def load(name: str) -> dict:
    with open(BASE / name, encoding="utf-8") as f:
        return json.load(f)


pairs = []

# ═══ 1) 确定注入：fuzuo（辅星×宫）═══
fz = load("ziwei_fuzuo.json")
fuzuo_pairs = [
    ("天魁", "命宮", "天魁星落在命宫有什么影响"),
    ("文昌", "官祿", "文昌星在官禄宫主什么"),
    ("文昌", "命宮", "文昌星落在命宫说明这个人怎样"),
    ("天钺", "夫妻", "天钺在夫妻宫代表什么"),
    ("左辅", "官祿", "左辅在官禄宫主什么"),
    ("右弼", "命宮", "右弼坐命的人如何"),
    ("文曲", "官祿", "文曲在官禄宫主什么"),
    ("禄存", "命宮", "禄存在命宫代表什么"),
    ("天马", "迁移", "天马在迁移宫主什么"),
    ("擎羊", "命宮", "擎羊坐命有什么影响"),
    ("陀罗", "財帛", "陀罗在财帛宫好不好"),
    ("火星", "夫妻", "火星在夫妻宫代表什么"),
    ("铃星", "官祿", "铃星在官禄宫主什么"),
    ("地空", "命宮", "地空坐命的人如何"),
    ("地劫", "田宅", "地劫在田宅宫代表什么"),
]
for i, (star, pal, q) in enumerate(fuzuo_pairs):
    assert star in fz and pal in fz[star]["分宫"], (star, pal)
    pairs.append({
        "id": f"zf_{i+1:03d}", "query": q,
        "target": {"file": "ziwei_fuzuo.json", "key": {"star": star, "palace": pal}},
        "keywords": [star, pal],
        "tier": "named_generic", "note": "辅星×宫，白话问"
    })

# ═══ 2) 确定注入：classics.json（格局名→原文引文）═══
cj = load("ziwei_classics.json")
patterns = cj["patterns"]
classics_pairs = [
    ("紫府同宫", "紫府同宫是什么格局，好不好"),
    ("君臣庆会", "君臣庆会是什么意思"),
    ("日月并明", "日月并明这个格局代表什么"),
    ("月朗天门", "月朗天门什么意思"),
    ("日照雷门", "日照雷门是什么格局"),
    ("机月同梁格", "机月同梁格代表什么"),
    ("府相朝垣", "府相朝垣是什么意思"),
    ("火贪格", "火贪格是什么格局"),
    ("铃贪格", "铃贪格好不好"),
    ("三奇嘉会", "三奇嘉会代表什么"),
    ("禄马交驰", "禄马交驰是什么格局"),
    ("命宫化权", "命宫化权是什么意思"),
    ("火铃夹命", "火铃夹命是什么格局，吉凶如何"),
    ("辅弼夹命", "辅弼夹命是什么意思"),
    ("紫微独坐", "紫微独坐命宫是什么格局"),
    ("巨日同宫", "巨日同宫是什么格局"),
    ("杀破狼格", "杀破狼格代表什么"),
]
for i, (pat, q) in enumerate(classics_pairs):
    assert pat in patterns, pat
    pairs.append({
        "id": f"zc_{i+1:03d}", "query": q,
        "target": {"file": "ziwei_classics.json", "key": pat},
        "keywords": [pat],
        "tier": "named_generic", "note": "格局名问，答案=引文+按语，字面不重叠"
    })

# ═══ 3) 工具可达：star_palace（主星×宫）═══
sp = load("ziwei_star_palace.json")
stars = sp["stars"]
star_palace_pairs = [
    ("紫微", "命宮", "紫微坐命宫的人性格怎么样"),
    ("天机", "夫妻", "天机星落在夫妻宫代表什么"),
    ("太阳", "財帛", "太阳星在财帛宫好不好"),
    ("贪狼", "疾厄", "贪狼在疾厄宫是什么意思"),
    ("武曲", "官祿", "武曲星在官禄宫主事业怎么样"),
    ("天同", "命宮", "天同坐命的人性格怎么样"),
    ("廉贞", "夫妻", "廉贞星落在夫妻宫代表什么"),
    ("天府", "財帛", "天府在财帛宫的人财运怎么样"),
    ("太阴", "官祿", "太阴星在官禄宫主什么"),
    ("紫微", "田宅", "紫微在田宅宫好不好"),
    ("天机", "疾厄", "天机星在疾厄宫是什么意思"),
    ("太阳", "夫妻", "太阳落在夫妻宫说明什么"),
    ("武曲", "命宮", "武曲坐命的人有什么特点"),
    ("天同", "福德", "天同在福德宫主什么"),
    ("廉贞", "官祿", "廉贞在官禄宫的事业运如何"),
    ("天府", "命宮", "天府坐命的人性格如何"),
    ("太阴", "夫妻", "太阴在夫妻宫代表什么"),
    ("贪狼", "官祿", "贪狼在官禄宫说明什么"),
    ("巨门", "命宮", "巨门坐命的人有什么特点"),
    ("天相", "夫妻", "天相在夫妻宫主什么"),
    ("天梁", "財帛", "天梁在财帛宫好不好"),
    ("七杀", "官祿", "七杀在官禄宫的事业运"),
    ("破军", "命宮", "破军坐命的人性格怎么样"),
    ("天相", "疾厄", "天相在疾厄宫是什么意思"),
    ("天梁", "命宮", "天梁坐命的人如何"),
    ("七杀", "夫妻", "七杀落在夫妻宫代表什么"),
    ("破军", "財帛", "破军在财帛宫财运如何"),
    ("太阴", "疾厄", "太阴在疾厄宫代表什么"),
    ("天机", "官祿", "天机在官禄宫的事业"),
    ("紫微", "夫妻", "紫微在夫妻宫怎么样"),
]
for i, (star, pal, q) in enumerate(star_palace_pairs):
    assert star in stars and pal in stars[star]["palaces"], (star, pal)
    pairs.append({
        "id": f"zp_{i+1:03d}", "query": q,
        "target": {"file": "ziwei_star_palace.json", "key": {"star": star, "palace": pal}},
        "keywords": [star, pal],
        "tier": "dedicated", "note": "主星×宫，工具可达层"
    })

# ═══ 4) 工具可达：hua（四化×宫）═══
hua = load("ziwei_hua.json")
interp = hua["interpretation"]
hua_pairs = [
    ("化祿", "命宮", "化禄在命宫代表什么"),
    ("化忌", "疾厄", "化忌落在疾厄宫是什么意思"),
    ("化祿", "夫妻", "化禄在夫妻宫代表什么"),
    ("化祿", "官祿", "化禄在官禄宫主什么"),
    ("化祿", "遷移", "化禄在迁移宫好不好"),
    ("化權", "命宮", "化权在命宫代表什么"),
    ("化權", "財帛", "化权在财帛宫主什么"),
    ("化權", "官祿", "化权在官禄宫的事业"),
    ("化科", "命宮", "化科在命宫代表什么"),
    ("化科", "夫妻", "化科在夫妻宫主什么"),
    ("化科", "財帛", "化科在财帛宫说明什么"),
    ("化忌", "命宮", "化忌在命宫代表什么"),
    ("化忌", "夫妻", "化忌在夫妻宫代表什么"),
    ("化忌", "財帛", "化忌在财帛宫好不好"),
    ("化忌", "遷移", "化忌在迁移宫说明什么"),
]
for i, (h, pal, q) in enumerate(hua_pairs):
    assert h in interp and pal in interp[h]["in_palace_guide"], (h, pal)
    pairs.append({
        "id": f"zh_{i+1:03d}", "query": q,
        "target": {"file": "ziwei_hua.json", "key": {"hua": h, "palace": pal}},
        "keywords": [h, pal],
        "tier": "generic_by_design", "note": "四化×宫，star 留空（化曜级通用解读）"
    })

# ═══ 5) 计划扩展：classics_full（文言 13 条 + 白话控制组）═══
cf = load("ziwei_classics_full.json")
paras = cf["paragraphs"]
wenyan_idx = {0, 1, 2, 23, 29, 30, 31, 32, 44, 58, 65, 66, 67}
classics_full_pairs = [
    (7, "七杀这颗星性格上有什么特点", ["七杀"]),
    (39, "巨门为什么被人说成口舌是非之曜", ["巨门", "口舌"]),
    (68, "生年四化是不是固定不变的", ["生年四化", "四化"]),
    (0, "紫微和天府这些星曜在斗数里是什么地位", ["紫微", "天府"]),
    (1, "斗数里辅佐帝星的星曜有哪些", ["左辅", "右弼", "紫微"]),
    (2, "看命的时候先看什么", ["命宫", "身宫"]),
    (23, "羊陀夹忌是什么，凶不凶", ["羊陀夹忌", "化忌"]),
    (29, "紫微斗数是什么人传下来的", ["陈抟", "紫微斗数"]),
    (30, "命盘里的星是怎么安上去的", ["安星", "年干"]),
    (31, "命宫和身宫各代表什么", ["命宫", "身宫"]),
    (32, "紫微这颗星有什么特质", ["紫微", "帝座"]),
    (44, "太阳这颗星主什么", ["太阳", "男贵"]),
    (58, "命宫在一张盘里是什么地位", ["命宫", "枢纽"]),
    (65, "夫妻宫主要看什么", ["夫妻宫", "配偶"]),
    (66, "夫妻宫化忌代表什么", ["夫妻宫", "化忌"]),
    (67, "四化各自主什么", ["化禄", "化权", "化科", "化忌"]),
]
for i, (idx, q, kws) in enumerate(classics_full_pairs):
    assert 0 <= idx < len(paras), idx
    pairs.append({
        "id": f"cff_{i+1:03d}", "query": q,
        "target": {"file": "ziwei_classics_full.json", "key": {"index": idx}},
        "keywords": kws,
        "tier": "generic_by_design",
        "status": "graduated",  # full 不登记 schema，登记化后 dispatch 拒绝绕道测；已毕业留档，dry-run 跳过
        "note": "文言转述池" if idx in wenyan_idx else "白话转述（控制组）"
    })

# ═══ 6) 直读表：tiaohou ═══
th = load("tiaohou.json")
table = th["table"]
tiaohou_pairs = [
    ("甲", "寅", "甲日出生在寅月调候用什么天干"),
    ("乙", "丑", "乙日生在丑月调候喜什么"),
    ("丙", "午", "丙日午月调候用什么"),
    ("丁", "卯", "丁日卯月调候用神是什么"),
    ("戊", "申", "戊日申月调候喜什么"),
    ("己", "亥", "己日亥月调候用什么"),
    ("庚", "巳", "庚日巳月调候用神"),
    ("辛", "子", "辛日子月调候喜什么"),
    ("壬", "酉", "壬日酉月调候用什么"),
    ("癸", "辰", "癸日辰月调候用神是什么"),
]
for i, (gan, zhi, q) in enumerate(tiaohou_pairs):
    assert gan in table and zhi in table[gan], (gan, zhi)
    pairs.append({
        "id": f"th_{i+1:03d}", "query": q,
        "target": {"file": "tiaohou.json", "key": {"gan": gan, "zhi": zhi}},
        "keywords": [gan, zhi],
        "tier": "generic_by_design", "note": "调候表精确查询"
    })

# ═══ 组装 + 校验 ═══
meta = {
    "version": "0.2",
    "judge": "exact_contain",
    "k": 5,
    "normalize": "去空白/全半角/标点后，标准答案文本为返回段落子串即算中",
    "validation": "star/hua 类 target：palace 必填，star 与 hua 至少一者非空；classics 用 index/格局名；tiaohou 用 gan/zhi；keywords=模拟命盘检索词，新旧检索器共用",
    "whitelist_ref": "kb_whitelist.json (content_hash 由 kb_whitelist_hash.py 唯一算法源计算)",
    "note": "v0.2 扩池：6 组 target 形态，答案不硬编码，评测时从 KB 对应 target 实时取"
}
out = {"meta": meta, "pairs": pairs}

# 校验：target 全部在 KB 中存在
errs = []
for p in pairs:
    t = p["target"]
    fn = t["file"]
    kb = load(fn)
    if fn == "ziwei_classics_full.json":
        n = len(kb["paragraphs"])
        if not (0 <= t["key"]["index"] < n):
            errs.append((p["id"], "index out of range"))
    elif fn == "ziwei_classics.json":
        if t["key"] not in kb["patterns"]:
            errs.append((p["id"], "pattern not found"))
    elif fn == "tiaohou.json":
        if t["key"]["gan"] not in kb["table"] or t["key"]["zhi"] not in kb["table"][t["key"]["gan"]]:
            errs.append((p["id"], "tiaohou key missing"))
    elif fn == "ziwei_hua.json":
        if t["key"]["hua"] not in kb["interpretation"]:
            errs.append((p["id"], "hua missing"))
        elif t["key"]["palace"] not in kb["interpretation"][t["key"]["hua"]]["in_palace_guide"]:
            errs.append((p["id"], "hua palace missing"))
    else:
        star = t["key"]["star"]
        pal = t["key"]["palace"]
        if fn == "ziwei_star_palace.json":
            if star not in kb["stars"] or pal not in kb["stars"][star]["palaces"]:
                errs.append((p["id"], "star/palace missing"))
        elif fn == "ziwei_fuzuo.json":
            if star not in kb or pal not in kb[star]["分宫"]:
                errs.append((p["id"], "fuzuo star/palace missing"))
        else:
            errs.append((p["id"], f"unknown file {fn}"))

if errs:
    print("VALIDATION FAILED:", errs)
    raise SystemExit(1)

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

tier_count = {}
for p in pairs:
    tier_count[p["tier"]] = tier_count.get(p["tier"], 0) + 1
print(f"OK: {len(pairs)} pairs written to {OUT.name}")
print("tier distribution:", tier_count)
