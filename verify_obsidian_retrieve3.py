# -*- coding: utf-8 -*-
"""最终复验：联合键修复后 line_tags 输出（湘生改完，2026-08-14）。
⚠️ 已过期：管道逻辑以 services/orchestrator 为准，本脚本 _rank_key 为旧单键版
（只认古籍原文，不含古籍数字化平台），仅作历史行为参照，勿用于验证（2026-08-14 标注）。
"""
import sys, os, json, re
BASE = r"D:\OH-WorkSpace\Destiny_agent"
sys.path.insert(0, BASE)
from knowledge_base.obsidian_retriever import retrieve, evidence_pack

def _normalize(s):
    return (s or "").replace(" ", "").replace("\u3000", "")

# 复刻修复后的 hook 逻辑
meta_dir = os.path.join(BASE, "knowledge_base", "obsidian_meta")
cache = {}
for fn in os.listdir(meta_dir):
    if fn.endswith(".json"):
        cache[fn] = json.load(open(os.path.join(meta_dir, fn), encoding="utf-8"))

def _rank_key(item):
    _s, h = item
    a = h.get("authority", "") or ""
    if "古籍原文" in a:
        return 0
    if h.get("type") in ("moc", "note"):
        return 1
    return 2

def tool_with_lines(query, top_k=3):
    hits = retrieve(query, top_k=50)
    hits.sort(key=lambda it: (_rank_key(it), -it[0]))
    per_line = {}
    for x in cache.get("style_tags_per_line.json", []):
        if x.get("PageId"):
            per_line[(str(x["PageId"]), str(x.get("行号")))] = x.get("文体", "")
    packs = []
    for _s, h in hits[:top_k]:
        ep = evidence_pack(h)
        tags = []
        for m in re.finditer(r"\|\s*\d+\s*\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|", h.get("body", "")):
            _ln, _lt, _pid, _txt = m.groups()
            if _normalize(_txt).find(_normalize(query)) >= 0 and (str(_pid), _ln) in per_line:
                tags.append({"行号": _ln, "PageId": _pid, "文体": per_line[(str(_pid), _ln)], "原文": _txt.strip()[:40]})
        if tags:
            ep["line_tags"] = tags[:6]
        packs.append(ep)
    return packs

print("=== 搜「禄逢冲破」：三跳行级标签 ===")
packs = tool_with_lines("禄逢冲破")
for p in packs:
    lt = p.get("line_tags")
    print(f"[{p.get('title')[:22]}] line_tags: {json.dumps(lt, ensure_ascii=False)[:220] if lt else '无'}")

print("\n=== 搜「凶」：抽查同页多行页（407/408 同 PageId）===")
packs = tool_with_lines("凶")
for p in packs:
    lt = p.get("line_tags")
    if lt:
        print(f"[{p.get('title')[:22]}]")
        for t in lt:
            print(f"  行{t['行号']} PageId={t['PageId']} 文体={t['文体']} | {t['原文']}")
