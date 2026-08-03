# -*- coding: utf-8 -*-
"""抽取《紫微斗数全书·卷一》格局诗（wikisource 公版）为结构化知识库

用法: python scripts/extract_geju.py
产出: knowledge_base/ziwei_geju.json
格式: {"paragraphs": [{"name": 格名, "condition": 成格条件原文, "poem": 诗句,
                       "source": "quanshu-geju", "school": "quanshu"}]}
成格条件与格名一起保留（hanako: 喂格局核验时用）
"""
import json
import re
import urllib.request

URL = 'https://zh.wikisource.org/w/index.php?title=%E7%B4%AB%E5%BE%AE%E6%96%97%E6%95%B8%E5%85%A8%E6%9B%B8/%E5%8D%B7%E4%B8%80&action=raw'
OUT = 'knowledge_base/ziwei_geju.json'


def clean_wikitext(s: str) -> str:
    s = re.sub(r'\[\[(?:[^|\]]*\|)?([^\]]+)\]\]', r'\1', s)
    s = re.sub(r"'''?", '', s)
    s = re.sub(r'<[^>]+>', '', s)
    return s.strip()


def main():
    req = urllib.request.Request(URL, headers={'User-Agent': 'Mozilla/5.0'})
    text = urllib.request.urlopen(req, timeout=60).read().decode('utf-8')

    i1 = text.find('论对面朝斗格')
    i2 = text.find('定富贵贫贱十等论')
    if i1 < 0 or i2 < 0:
        print('区间定位失败')
        return
    seg = text[i1:i2]

    # 按 '论' 开头切块
    blocks = re.split(r'(?=论[^\n])', seg)
    paragraphs = []
    for block in blocks:
        block = block.strip()
        if not block.startswith('论'):
            continue
        lines = block.split('\n')
        head = clean_wikitext(lines[0])
        body = clean_wikitext('\n'.join(lines[1:]))
        # name = 论 后第一个词（空格前），condition = 剩余
        head_body = head[1:].strip()  # 去掉'论'
        parts = head_body.split(' ', 1)
        name = parts[0]
        condition = parts[1] if len(parts) > 1 else ''
        paragraphs.append({
            'name': name,
            'condition': condition,
            'poem': body,
            'source': 'quanshu-geju',
            'school': 'quanshu',
        })

    # 过滤垃圾条目（诗长过短/条件为空且名字无意义）
    paragraphs = [p for p in paragraphs if len(p['poem']) >= 20]

    data = {'paragraphs': paragraphs}
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print('抽取格局数:', len(paragraphs))
    for p in paragraphs:
        print(' -', p['name'], '| 条件:', p['condition'][:30], '| 诗句长度', len(p['poem']))
    print('已写入', OUT)


if __name__ == '__main__':
    main()
