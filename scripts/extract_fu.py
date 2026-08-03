# -*- coding: utf-8 -*-
"""抽取《紫微斗数全书·卷一》赋文（wikisource 公版）为结构化知识库

用法: python scripts/extract_fu.py
产出: knowledge_base/ziwei_fu.json
格式: {"paragraphs": [{"title": 篇名, "text": 正文, "source": "quanshu-fu", "school": "quanshu"}]}
"""
import json
import re
import urllib.request

URL = 'https://zh.wikisource.org/w/index.php?title=%E7%B4%AB%E5%BE%AE%E6%96%97%E6%95%B8%E5%85%A8%E6%9B%B8/%E5%8D%B7%E4%B8%80&action=raw'
OUT = 'knowledge_base/ziwei_fu.json'

# 要抽取的赋文标题（按卷一次序）
TITLES = ['太微賦', '形性賦', '星垣論', '斗數準繩', '斗數發微論', '重補斗數彀率', '增補太微賦']


def clean_wikitext(s: str) -> str:
    s = re.sub(r'\[\[(?:[^|\]]*\|)?([^\]]+)\]\]', r'\1', s)
    s = re.sub(r"'''?", '', s)
    s = re.sub(r'<ref[^>]*>.*?</ref>', '', s, flags=re.S)
    s = re.sub(r'<[^>]+>', '', s)
    s = re.sub(r'^\s*={2,5}\s*', '', s)  # 去掉开头残留的标题闭合标记
    return s.strip()


def main():
    req = urllib.request.Request(URL, headers={'User-Agent': 'Mozilla/5.0'})
    text = urllib.request.urlopen(req, timeout=60).read().decode('utf-8')

    # 找所有标题位置 (起点, 标题, 终点含闭合标记)
    heads = [(m.start(), m.group(1), m.end()) for m in re.finditer(r'={2,5}\s*(.*?)\s*={2,5}', text)]

    paragraphs = []
    for i, (pos, title, head_end) in enumerate(heads):
        if title not in TITLES:
            continue
        # 正文 = 本标题闭合标记之后到下一个标题之间
        end = heads[i + 1][0] if i + 1 < len(heads) else len(text)
        body = clean_wikitext(text[head_end:end])
        if len(body) < 20:
            continue
        paragraphs.append({
            'title': title,
            'text': body,
            'source': 'quanshu-fu',
            'school': 'quanshu',
        })

    data = {'paragraphs': paragraphs}
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print('抽取赋文数:', len(paragraphs))
    for p in paragraphs:
        print(' -', p['title'], '| 长度', len(p['text']))
    print('已写入', OUT)


if __name__ == '__main__':
    main()
