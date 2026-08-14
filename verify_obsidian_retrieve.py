# -*- coding: utf-8 -*-
"""验证 kb_obsidian_retrieve 工具链路（2026-08-14 接线后）。
⚠️ 已过期：管道逻辑以 services/orchestrator 为准，本脚本的 _rank_key 为旧单键版
（只认古籍原文，不含古籍数字化平台），仅作历史行为参照，勿用于验证（2026-08-14 标注）。
复刻 orchestrator 的重排+打包逻辑，实测多个查询。
验证点：证据包格式 / 出处链完整性 / 古籍原文优先重排 / meta hook。
"""
import sys, os, json
BASE = r"D:\OH-WorkSpace\Destiny_agent"
sys.path.insert(0, BASE)
from knowledge_base.obsidian_retriever import retrieve, evidence_pack

# 复刻 orchestrator._obsidian_meta_tags
_META_DIR = os.path.join(BASE, "knowledge_base", "obsidian_meta")
def meta_tags(rel_file):
    out = {}
    if os.path.isdir(_META_DIR):
        for fn in os.listdir(_META_DIR):
            if fn.endswith(".json"):
                try:
                    data = json.load(open(os.path.join(_META_DIR, fn), encoding="utf-8"))
                    base = os.path.basename(rel_file)
                    for k, v in data.items():
                        if k == base or k in rel_file or rel_file.endswith(k):
                            out[fn.replace(".json", "")] = v
                except Exception:
                    pass
    return out

def tool(query, system="", top_k=5):
    sys_filter = system.strip() or None
    hits = retrieve(query, system=sys_filter, top_k=max(top_k * 3, 15))
    def _rank_key(item):
        _s, h = item
        a = h.get("authority", "") or ""
        if "古籍原文" in a:
            return 0
        if h.get("type") in ("moc", "note"):
            return 1
        return 2
    hits.sort(key=lambda it: (_rank_key(it), -it[0]))
    packs = []
    for _score, h in hits[:top_k]:
        ep = evidence_pack(h)
        ep["source_kb"] = "obsidian"
        ep["file"] = h["file"]
        ep["meta"] = meta_tags(h["file"])
        packs.append(ep)
    return packs

for q in ["禄逢冲破", "㐫", "七杀守命", "斗君"]:
    print(f"\n{'='*60}\n查询: {q}")
    packs = tool(q, top_k=5)
    print(f"命中 {len(packs)} 条:")
    for i, p in enumerate(packs):
        meta = p.get("meta") or {}
        mstr = f"meta={meta}" if meta else "meta=空"
        print(f"  {i}. [{p.get('type')}] auth={str(p.get('authority'))[:16]:18} url={'有' if p.get('url') else '无':3} | {str(p.get('title'))[:36]} {mstr}")
    # 检查第一条（应为古籍原文）的出处链
    if packs:
        p0 = packs[0]
        print(f"  首条出处链: url={p0.get('url')!r} source={p0.get('source')!r}")

# 验证：363 素材的 evidence_pack 完整性
print(f"\n{'='*60}\n363 素材证据包完整性")
hits = retrieve("禄逢冲破", top_k=30)
for _s, h in hits:
    if "2026-08-14-sdzj0170-xiong-context" in h.get("file", ""):
        ep = evidence_pack(h)
        print("  file:", h["file"])
        for k in ["title", "url", "source", "authority", "system", "type", "status"]:
            print(f"    {k}: {ep.get(k)!r}")
        print("    excerpt 长度:", len(ep.get("excerpt", "")))
        break
