# -*- coding: utf-8 -*-
"""抽取《紫微斗数全书·卷一·诸星问答论》(wikisource 公版) 为结构化知识库

用法: python scripts/extract_qawenlun.py
产出: knowledge_base/ziwei_qawenlun.json
格式: {"paragraphs": [{"star": 星名, "question": 问句, "text": 答文, "source": "quanshu-qawenlun"}]}
四道关: 公版(清朝公有领域✓) / 口径(星曜特质问答, 无排盘冲突) / 安星诀(无) / 别名(提取古籍用词进 _STAR_ALIAS)
"""
import json
import re
import urllib.request

URL = 'https://zh.wikisource.org/w/index.php?title=%E7%B4%AB%E5%BE%AE%E6%96%97%E6%95%B8%E5%85%A8%E6%9B%B8/%E5%8D%B7%E4%B8%80&action=raw'
OUT = 'knowledge_base/ziwei_qawenlun.json'


def clean_wikitext(s: str) -> str:
    """清理 wikitext 标记"""
    s = re.sub(r'\[\[(?:[^|\]]*\|)?([^\]]+)\]\]', r'\1', s)  # 链接
    s = re.sub(r"'''?", '', s)  # 粗斜体
    s = re.sub(r'<ref[^>]*>.*?</ref>', '', s, flags=re.S)
    s = re.sub(r'<[^>]+>', '', s)
    return s.strip()


def main():
    req = urllib.request.Request(URL, headers={'User-Agent': 'Mozilla/5.0'})
    text = urllib.request.urlopen(req, timeout=60).read().decode('utf-8')

    start = text.find('諸星問答論')
    end = text.find('斗數骨髓賦')
    if end < 0:
        end = text.find('斗数骨髓赋')
    seg = text[start:end if end > 0 else len(text)]

    # 按问答标题切分（标题前可带可不带 === 标记；[問问] 繁简兼容）
    q_pat = re.compile(
        r'(?:={2,5}\s*)?([問问][^=]{2,20}?[？?])\s*={2,5}(.*?)'
        r'(?=(?:={2,5}\s*)?[問问][^=]{2,20}?[？?]\s*={2,5}|\Z)', re.S)
    paragraphs = []
    for m in q_pat.finditer(seg):
        question = m.group(1).strip()
        answer = clean_wikitext(m.group(2))
        if len(answer) < 10:
            continue
        # 星名提取：用已知星名表在问句中匹配（繁简双写；火星/铃星等带'星'字星名）
        _KNOWN = ['流年昌曲', '天哭天虚', '天空地劫', '天伤天使', '羊陀火铃', '羊陀',
                  '紫微', '天機', '天机', '太陽', '太阳', '武曲', '天同', '廉貞', '廉贞',
                  '天府', '太陰', '太阴', '貪狼', '贪狼', '巨門', '巨门', '天相', '天梁',
                  '七殺', '七杀', '破軍', '破军', '文昌', '文曲', '左輔', '左辅', '右弼',
                  '天魁', '天鉞', '天钺', '祿存', '禄存', '天馬', '天马', '化祿', '化禄',
                  '化權', '化权', '化科', '化忌', '擎羊', '陀羅', '陀罗', '火星', '鈴星',
                  '铃星', '地空', '地劫', '天刑', '天姚', '天哭', '天虛', '天虚']
        star = next((s for s in _KNOWN if s in question), question)
        # 星名归一化为简体（检索一致性）
        _TR = {'機': '机', '陽': '阳', '貞': '贞', '陰': '阴', '貪': '贪', '門': '门',
               '殺': '杀', '軍': '军', '輔': '辅', '鉞': '钺', '祿': '禄', '馬': '马',
               '權': '权', '羅': '罗', '鈴': '铃', '虛': '虚'}
        for k, v in _TR.items():
            star = star.replace(k, v)
        paragraphs.append({
            'star': star,
            'question': question,
            'text': answer,
            'source': 'quanshu-qawenlun',
            'school': 'quanshu',  # 体系标签：全书系（将来入中州/飞星系时检索按体系过滤，意象断语不混用）
        })

    data = {'paragraphs': paragraphs}
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print('抽取段落数:', len(paragraphs))
    for p in paragraphs[:5]:
        print(' -', p['star'], '|', p['question'], '|', p['text'][:40] + '...')
    print('已写入', OUT)


if __name__ == '__main__':
    main()
