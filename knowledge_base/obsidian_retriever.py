#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Obsidian 知识库检索模块（knowledge_base/obsidian/ 派生副本的只读检索）

设计（2026-08-11 团队共识）：
- 分层：口径层（disambiguation/note，引擎基准）提权；素材层（网页快照）按需命中
- 过滤：status=raw 优先级低（digested 优先）；authority 排序（本人确认 > 古籍原文 > 官方 > 百科 > 个人站）
- 消歧页提权：type: disambiguation 且 title 命中 → 第一落点（跨体系词先分流）
- 返回证据包：frontmatter + 正文截断（结论+出处链整包，接 Agent 注入直接可用）
- 本模块只读派生副本；真源在私有仓 vault，由 scripts/sync_obsidian_to_kb.py 单向同步

用法：
    from knowledge_base.obsidian_retriever import retrieve
    hits = retrieve('四化', system='飞星')
"""
import os
import re

_KB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'obsidian')

AUTHORITY_ORDER = ['本人确认', '古籍原文', '官方', '百科', '个人站']

# ── 简繁+异体归一（2026-08-14 hanako 验出缺陷、mose 补异体坑后加） ──
# opencc t2s 处理繁简；异体字 opencc 不覆盖，用表补充（㐫/凶/兇 互通为卷二 431 实证）
_VARIANT_MAP = {
    '㐫': '凶',
    '兇': '凶',
    '䧟': '陷',
    '𢙣': '恶',
    '𠔥': '兼',
    '尢': '尤',
}
_NORM_CC = None


def _normalize(text: str) -> str:
    """简繁归一（t2s）+ 异体字归一，供检索匹配；不改变原文存储。"""
    global _NORM_CC
    if not text:
        return ""
    if _NORM_CC is None:
        try:
            from opencc import OpenCC
            _NORM_CC = OpenCC('t2s')
        except Exception:
            _NORM_CC = None
    s = _NORM_CC.convert(text) if _NORM_CC else text
    for v, n in _VARIANT_MAP.items():
        s = s.replace(v, n)
    return s


def _parse_frontmatter(text):
    """解析 md frontmatter（简易 key: value，含列表只取首项）"""
    fm = {}
    m = re.match(r'^---\n(.*?)\n---', text, re.DOTALL)
    if not m:
        return fm
    for line in m.group(1).splitlines():
        if ':' in line and not line.startswith('-'):
            k, v = line.split(':', 1)
            fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm


def _authority_rank(fm):
    a = fm.get('authority', '')
    return AUTHORITY_ORDER.index(a) if a in AUTHORITY_ORDER else len(AUTHORITY_ORDER)


def _load_all():
    docs = []
    for root, _dirs, files in os.walk(_KB_DIR):
        for f in files:
            if not f.endswith('.md'):
                continue
            path = os.path.join(root, f)
            with open(path, encoding='utf-8') as fh:
                text = fh.read()
            fm = _parse_frontmatter(text)
            body = re.sub(r'^---\n.*?\n---\n', '', text, flags=re.DOTALL)
            docs.append({
                'file': os.path.relpath(path, _KB_DIR).replace(os.sep, '/'),
                'title': fm.get('title', f),
                'title_norm': _normalize(fm.get('title', f)),
                'status': fm.get('status', ''),
                'authority': fm.get('authority', ''),
                'system': fm.get('system', ''),
                'type': fm.get('type', ''),
                'url': fm.get('url', ''),
                'source': fm.get('source', ''),
                'body': body,
                'body_norm': _normalize(body),
            })
    return docs


def retrieve(term, system=None, top_k=5, _docs=None):
    """关键词检索，返回按 消歧页提权 + digested 优先 + authority 排序的证据包列表"""
    if _docs is None:
        _docs = _load_all()
    t = _normalize(term)
    t = t.strip()
    if not t:
        return []

    scored = []
    for d in _docs:
        if system and d['system'] and system != d['system']:
            continue
        title_hit = t in d.get('title_norm', '')
        body_hit = t in d.get('body_norm', '')
        if not (title_hit or body_hit):
            continue
        # 计分：title 命中 > body 命中；消歧页提权；digested > raw；authority 排序
        score = (10 if title_hit else 1) + (0 if body_hit else 0)
        if d['type'] == 'disambiguation':
            score += 100
        if d['status'] == 'digested':
            score += 20
        elif d['status'] == 'raw':
            score -= 20
        score -= _authority_rank(d) * 2
        scored.append((score, d))

    scored.sort(key=lambda x: -x[0])
    return scored[:top_k]


def evidence_pack(hit, body_chars=1200):
    """证据包：结论+出处链整包（接 Agent 注入）"""
    body = re.sub(r'\n{3,}', '\n\n', hit['body']).strip()
    return {
        'title': hit['title'],
        'url': hit['url'],
        'source': hit['source'],
        'status': hit['status'],
        'authority': hit['authority'],
        'system': hit['system'],
        'type': hit['type'],
        'excerpt': body[:body_chars],
    }


if __name__ == '__main__':
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else '四化'
    sys_filter = sys.argv[2] if len(sys.argv) > 2 else None
    hits = retrieve(q, system=sys_filter)
    print(f'== query: {q} (system={sys_filter}) ==')
    for _score, h in hits:
        ep = evidence_pack(h)
        print(f"[{ep['type']}] {ep['title']} | status={ep['status']} authority={ep['authority']} system={ep['system']} | file={h['file']}")
        print(f"    excerpt: {ep['excerpt'][:100].replace(chr(10), ' ')}")
