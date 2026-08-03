# -*- coding: utf-8 -*-
"""抽取《紫微斗数全书·卷三》星曜分宫断语（wikisource 公版）

用法: python scripts/extract_juan3.py
产出: knowledge_base/ziwei_juan3.json
格式: {"paragraphs": [{"star": 星名, "miao": 庙旺陷标记, "text": 断语集,
                       "source": "quanshu-juan3", "school": "quanshu"}]}
"""
import json
import re
import urllib.request

URL = 'https://zh.wikisource.org/w/index.php?title=%E7%B4%AB%E5%BE%AE%E6%96%97%E6%95%B8%E5%85%A8%E6%9B%B8/%E5%8D%B7%E4%B8%89&action=raw'
OUT = 'knowledge_base/ziwei_juan3.json'

# 卷三星曜断语区出现的星名（按文本顺序，长名优先；贪狼古籍写作'贪狠'）
STARS = ['左辅右弼', '紫微', '天府', '天相', '天梁', '天同', '天机', '太阳', '太阴',
         '文昌', '文曲', '武曲', '贪狠', '贪狼', '廉贞', '巨门', '七杀', '破军',
         '擎羊', '陀罗', '火星', '铃星', '魁钺', '禄存']


def clean_wikitext(s: str) -> str:
    s = re.sub(r'\[\[(?:[^|\]]*\|)?([^\]]+)\]\]', r'\1', s)
    s = re.sub(r"'''?", '', s)
    s = re.sub(r'<[^>]+>', '', s)
    s = re.sub(r'</?poem>', '', s)
    return s.strip()


def main():
    req = urllib.request.Request(URL, headers={'User-Agent': 'Mozilla/5.0'})
    text = urllib.request.urlopen(req, timeout=60).read().decode('utf-8')

    i1 = text.find('===论诸星同垣各司所宜分别富贵贫贱夭寿===')
    seg = text[i1:] if i1 >= 0 else text

    # 星名块切分：星名后可选庙旺陷标记（魁钺/左辅右弼无标记直接换行）
    pat = re.compile(
        r'^(' + '|'.join(sorted(STARS, key=len, reverse=True)) + r')(?:\s+[庙旺地平陷][^\n]*)?\n',
        re.M)
    matches = list(pat.finditer(seg))
    paragraphs = []
    for k, m in enumerate(matches):
        star = m.group(1)
        # 过滤正文误匹配（如'贪狠入庙寿元长'不是块头）
        if star == '贪狠' and not seg[m.end():m.end() + 6].startswith('<poem>'):
            continue
        if star == '贪狼':
            continue  # 与贪狠同源，跳过
        end = matches[k + 1].start() if k + 1 < len(matches) else len(seg)
        block = clean_wikitext(seg[m.start():end])
        lines = block.split('\n')
        miao_line = lines[0] if lines else ''
        miao = miao_line[len(star):].strip() if miao_line.startswith(star) else ''
        body = '\n'.join(lines[1:]).strip()
        if len(body) < 15:
            continue
        paragraphs.append({
            'star': star.replace('贪狠', '贪狼'),
            'miao': miao,
            'text': body,
            'source': 'quanshu-juan3',
            'school': 'quanshu',
        })

    data = {'paragraphs': paragraphs}
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print('抽取星曜断语:', len(paragraphs), '条')
    for p in paragraphs:
        print(' -', p['star'], '|', p['miao'][:20], '| 长度', len(p['text']))
    print('已写入', OUT)


if __name__ == '__main__':
    main()
