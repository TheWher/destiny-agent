# -*- coding: utf-8 -*-
"""复验 kb_obsidian_retrieve（湘生修复后）：简体/异体搜索、meta 三字段、证据包。
⚠️ 已过期：管道逻辑以 services/orchestrator 为准，本脚本 _rank_key 为旧单键版
（只认古籍原文，不含古籍数字化平台），仅作历史行为参照，勿用于验证（2026-08-14 标注）。
"""
import sys, os, json
BASE = r"D:\OH-WorkSpace\Destiny_agent"
sys.path.insert(0, BASE)
from knowledge_base.obsidian_retriever import retrieve, evidence_pack

# 复刻 orchestrator 重排（跟之前一致）
def _rank_key(item):
    _s, h = item
    a = h.get("authority", "") or ""
    if "古籍原文" in a:
        return 0
    if h.get("type") in ("moc", "note"):
        return 1
    return 2

def tool(query, system="", top_k=5, window=50):
    sys_filter = system.strip() or None
    hits = retrieve(query, system=sys_filter, top_k=window)
    hits.sort(key=lambda it: (_rank_key(it), -it[0]))
    packs = []
    for _score, h in hits[:top_k]:
        ep = evidence_pack(h)
        ep["source_kb"] = "obsidian"
        ep["file"] = h["file"]
        packs.append(ep)
    return packs

print("=== 复验 1：简体搜索 ===")
for q in ["七杀守命", "凶", "陷地", "七杀"]:
    packs = tool(q, top_k=5)
    print(f"\n查询「{q}」→ {len(packs)} hits:")
    for i, p in enumerate(packs):
        hit363 = "✔363" if "2026-08-14" in p.get("file", "") else "   "
        print(f"  {i}. {hit363} [{p.get('type')}] auth={str(p.get('authority'))[:14]:16} | {str(p.get('title'))[:34]}")

print("\n=== 复验 2：meta 三字段 ===")
# 直接看 obsidian_retriever 的证据包是否带 meta（湘生说 hook 适配了，但 hook 在 orchestrator；
# 这里检查 orchestrator 的 meta 读取是否生效——直接调 orchestrator 太重，改为验证 obsidian_meta 文件存在+内容）
meta_dir = os.path.join(BASE, "knowledge_base", "obsidian_meta")
print("obsidian_meta 存在:", os.path.isdir(meta_dir))
if os.path.isdir(meta_dir):
    for fn in sorted(os.listdir(meta_dir)):
        fp = os.path.join(meta_dir, fn)
        if fn.endswith(".json"):
            d = json.load(open(fp, encoding="utf-8"))
            n = len(d) if isinstance(d, (dict, list)) else "?"
            print(f"  {fn}: {n} 条 | {str(d)[:110]}")

print("\n=== 复验 3：双源命中（Obsidian 优先声明）===")
packs = tool("禄逢冲破", top_k=3)
p0 = packs[0]
print("首条:", p0.get("title"), "| source_kb:", p0.get("source_kb"))
print("note 字段（在 orchestrator 里，此处为工具层模拟，略）")
