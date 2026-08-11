#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""知识库验收：检索回归 + 全库 frontmatter 卫生巡检

验收点（2026-08-11）：
1. 模型遇到跨体系术语（四化）会不会走消歧页分流
2. 模型会不会引用出处链（authority/来源）
3. 检索命中是否准确
4. frontmatter 卫生（tags 无代码残留/重复、必填字段齐全）——2026-08-11 春鳥橋抓出 tags 残留 bug 后补

触发约定（2026-08-11 定）：凡改 frontmatter、检索模块或加术语消歧页，必跑本脚本
（--all 快速回归 + 卫生巡检；单词模式做 LLM 深度验证）。术语面扩展时往 REGRESSION_TERMS 加词。

用法：
    python scripts/verify_kb_e2e.py [查询词]   # 单词 + LLM 深度验证
    python scripts/verify_kb_e2e.py --all      # 回归词表 + 全库卫生巡检（不调 LLM）
    python scripts/verify_kb_e2e.py --health   # 仅全库卫生巡检
"""
import sys
import os
import re

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from knowledge_base.obsidian_retriever import retrieve, evidence_pack, _parse_frontmatter
from services.llm_client import _call_api

_KB_DIR = os.path.join(_ROOT, 'knowledge_base', 'obsidian')

# 回归词表（选词标准 2026-08-11 定）：优先收“两系都用但含义不同”的跨体系术语（消歧页的料），
# 单系术语不进，避免噪音稀释回归信号；核心单系概念可例外（如来因宫=引擎第一落点，检索不可挂）
REGRESSION_TERMS = ['化忌', '庙旺', '四化', '来因宫']  # 来因宫：核心单系例外

REQUIRED_FM = ['title', 'url', 'source', 'fetched_at', 'status', 'type', 'content_mode']
REQUIRED_NOTE = ['title', 'type']  # 笔记/MOC/消歧页只需 title+type，其余字段各自规范
CODE_LEAK = re.compile(r'\.TrimEnd\(\)|\.strip\(\)|Out-String|ForEach-Object|\$it\.', re.I)


def health_check():
    """全库 frontmatter 卫生巡检：必填字段、tags 格式、无代码残留（跳过模板/欢迎/空文件）"""
    skip = {'模板', '欢迎.md', '2026-08-11.md'}
    files = []
    for root, _dirs, fs in os.walk(_KB_DIR):
        for f in fs:
            if not f.endswith('.md'):
                continue
            rel = os.path.relpath(os.path.join(root, f), _KB_DIR).replace(os.sep, '/')
            if rel in skip or rel.startswith('模板/'):
                continue
            files.append(os.path.join(root, f))
    fail = 0
    for path in sorted(files):
        text = open(path, encoding='utf-8').read()
        fm = _parse_frontmatter(text)
        rel = os.path.relpath(path, _KB_DIR).replace(os.sep, '/')
        errs = []
        # 按类型区分字段要求：素材查素材字段集，笔记/MOC/消歧页查基础字段集
        required = REQUIRED_NOTE if fm.get('type') in ('note', 'moc', 'disambiguation') else REQUIRED_FM
        for k in required:
            if not fm.get(k):
                errs.append(f'缺 {k}')
        raw_fm = re.match(r'^---\n(.*?)\n---', text, re.DOTALL)
        if raw_fm and CODE_LEAK.search(raw_fm.group(1)):
            errs.append('代码残留')
        tags = re.findall(r'^\s*-\s*(.+)$', raw_fm.group(1) if raw_fm else '', re.M)
        seen = set()
        for t in tags:
            t = t.strip()
            if not t:
                errs.append('空 tag')
            elif t in seen:
                errs.append(f'tag 重复:{t}')
            seen.add(t)
        if errs:
            print(f'FAIL {rel}: {errs}')
            fail += 1
    print(f'== health: {len(files) - fail}/{len(files)} files clean ==')
    return fail


def quick_regression():
    """不调 LLM：检查每个词有命中，且命中首条类型合理（消歧页词首条必须是 disambiguation）"""
    fail = 0
    for term in REGRESSION_TERMS:
        hits = retrieve(term, top_k=5)
        if not hits:
            print(f'FAIL {term}: 零命中')
            fail += 1
            continue
        top_type = hits[0][1]['type']
        # 消歧页词（标题含消歧）应提权到首条
        disambig = [h for h in hits if h[1]['type'] == 'disambiguation']
        if disambig and disambig[0][1]['title'] != hits[0][1]['title']:
            print(f'FAIL {term}: 消歧页未提权（{hits[0][1]["title"]} 排在了前面）')
            fail += 1
            continue
        print(f'PASS {term}: top=[{top_type}] {hits[0][1]["title"]}（{len(hits)} 条）')
    print(f'== regression: {len(REGRESSION_TERMS) - fail}/{len(REGRESSION_TERMS)} pass ==')
    return fail


def main():
    if '--health' in sys.argv:
        sys.exit(1 if health_check() else 0)
    if '--all' in sys.argv:
        fail = health_check() + quick_regression()
        sys.exit(1 if fail else 0)
    q = sys.argv[1] if len(sys.argv) > 1 else '化忌'
    print(f'== 检索: {q} ==')
    hits = retrieve(q, top_k=5)
    if not hits:
        print('!! 检索零命中')
        return

    refs = []
    for _score, h in hits:
        ep = evidence_pack(h, body_chars=700)
        meta = f"[{ep['type']}|{ep['authority'] or '未标'}|{ep['system'] or '通用'}|{ep['status'] or '-'}]"
        refs.append(f"{meta} 《{ep['title']}》 来源:{ep['url'] or ep['source'] or '本地笔记'}\n{ep['excerpt']}")
    kb_block = "\n\n---\n\n".join(refs)

    system_prompt = (
        "你是紫微斗数命理解读助手。下方是知识库检索到的参考资料，每条带 [类型|权威性|体系|状态] 标注。"
        "规则：1) 回答优先依据参考资料；2) 遇到跨体系术语（如四化）先说明体系归属，不要混用两套话语；"
        "3) 引用资料内容时标注出处来源。"
    )
    user_msg = f"参考资料：\n{kb_block}\n\n问题：命盘里化忌怎么解读？"

    print(f'== 注入 prompt（参考 {len(refs)} 条）==')
    r = _call_api(system_prompt, [{"role": "user", "content": user_msg}],
                  max_tokens=900, temperature=0.3, timeout=180)
    if not r.get('success'):
        print(f'!! API 失败: {r.get("error")}')
        return
    print('=== 模型回答 ===')
    print(r['text'])
    print(f"\n(model={r.get('model')} usage={r.get('usage')})")


if __name__ == '__main__':
    main()
