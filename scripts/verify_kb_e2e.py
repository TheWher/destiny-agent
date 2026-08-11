#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""端到端验收：知识库检索 → 证据包 → Agent prompt 注入 → 模型回答

验收点（2026-08-11 mose 提）：
1. 模型遇到跨体系术语（四化）会不会走消歧页分流
2. 模型会不会引用出处链（authority/来源）
3. 检索命中是否准确

用法：python scripts/verify_kb_e2e.py [查询词]
"""
import sys
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from knowledge_base.obsidian_retriever import retrieve, evidence_pack
from services.llm_client import _call_api


def main():
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
