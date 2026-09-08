# -*- coding: utf-8 -*-
"""知识库数据质量检查 2026-08-14（King 委托）。输出 qc_kb_report_20260814.txt"""
import os, json, re, io, sys
from collections import Counter
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
BASE = r"D:\OH-WorkSpace\Destiny_agent"
sys.path.insert(0, BASE)
from knowledge_base.obsidian_retriever import _load_all, retrieve, _normalize, _KB_DIR

out = []
def log(*a):
    s = ' '.join(str(x) for x in a)
    print(s); out.append(s)

docs = _load_all()

log('=== 1. 文档统计 ===')
log('文档总数:', len(docs))
log('type 分布:', dict(Counter(d['type'] for d in docs)))
log('authority 分布:', dict(Counter(d['authority'] for d in docs)))
log('status 分布:', dict(Counter(d['status'] for d in docs)))
log('system 分布:', dict(Counter(d['system'] for d in docs)))
missing = {}
for f in ['title','authority','status','system','type','url','source']:
    n = sum(1 for d in docs if not d[f])
    if n: missing[f] = n
log('frontmatter 缺失:', missing if missing else '无')

log('')
log('=== 2. 挂账项1：全覽「禄逢冲破」line_tags 根因 ===')
for d in docs:
    if 'quanlan' in d['file']:
        body = d['body']
        has_table = bool(re.search(r'^\s*\|', body, re.M))
        log(f"file={d['file']}")
        log(f"  title={d['title']} | type={d['type']} | authority={d['authority']} | status={d['status']}")
        log(f"  含表格行结构: {has_table} | body 长度: {len(body)}")
        for i, line in enumerate(body.splitlines()[:60]):
            if '祿逢' in line or '禄逢' in line:
                log(f"  原文命中 行{i}: {line[:70]}")
# 对照：SDZJ0170 juan2 表格结构样本
log('')
log('  [对照] SDZJ0170-juan2 表格结构样本:')
for d in docs:
    if 'sdzj0170-juan2' in d['file']:
        for line in d['body'].splitlines():
            if re.match(r'^\s*\|', line) and '禄逢' in line:
                log(f"    {line[:90]}")
                break
        break

log('')
log('=== 3. style_tags_per_line 概览 ===')
meta_dir = os.path.join(BASE, 'knowledge_base', 'obsidian_meta')
stpl = json.load(open(os.path.join(meta_dir, 'style_tags_per_line.json'), encoding='utf-8'))
log('行级标注条数:', len(stpl), '| 不同 PageId:', len(set(x.get('PageId') for x in stpl)))
log('文体分布:', dict(Counter(x.get('文体','') for x in stpl).most_common()))
st = json.load(open(os.path.join(meta_dir, 'style_tags.json'), encoding='utf-8'))
log('style_tags.json 键:', list(st.keys()) if isinstance(st, dict) else type(st).__name__)

log('')
log('=== 4. 检索抽查（top5） ===')
for q in ['禄逢冲破', '凶', '七杀', '四化']:
    hits = retrieve(q, top_k=5)
    log(f"query={q} 命中 {len(hits)}")
    for s, h in hits:
        log(f"  [{h['type']}] {h['title'][:28]} | auth={h['authority']} status={h['status']} | {h['file'][:56]}")

log('')
log('=== 5. 归一化验证 ===')
for t in ['祿逢沖破', '㐫', '兇', '䧟', '𢙣', '吉處藏凶', '馬遇空亡']:
    log(f"  {t!r} -> {_normalize(t)!r}")

report = os.path.join(BASE, 'qc_kb_report_20260814.txt')
open(report, 'w', encoding='utf-8').write('\n'.join(out))
print('SAVED:', report)
