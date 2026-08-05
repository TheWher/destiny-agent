# -*- coding: utf-8 -*-
"""修复验收：样本盘 12 宫功能名 vs mose js 金表 + 六宫摘要 + 四化/格局冒烟"""
import sys
sys.path.insert(0, '.')
from ziwei_calculator import ziwei_paipan, get_horoscope, detect_patterns, plate_to_dict

JS_GOLD = ['父母', '福德', '田宅', '官禄', '交友', '迁移', '疾厄', '财帛', '子女', '夫妻', '兄弟', '命宫']
TR = {'祿': '禄', '遷': '迁', '財': '财', '宮': '宫'}

def norm(s):
    for k, v in TR.items():
        s = s.replace(k, v)
    return s

pl = ziwei_paipan(1998, 6, 15, 10, 30, '男')
print('=== 验收1: 样本盘 12 宫功能名 vs js 金表 ===')
ok = 0
for p in pl['palaces']:
    g = JS_GOLD[p['index']]
    name = norm(p['name'])
    mark = 'OK' if name == g else 'XX'
    if name == g:
        ok += 1
    print('%s index=%d 地支=%s 项目名=%s js金表=%s tags=%s' % (mark, p['index'], p['earthly_branch'], p['name'], g, p['tags']))
print('12 宫功能名: %d/12' % ok)

print()
print('=== 验收2: 关键六宫（AI 摘要底座）===')
for p in pl['palaces']:
    if p['name'] in ('命宮', '夫妻', '財帛', '官祿', '遷移', '福德'):
        stars = '、'.join(s['name'] for s in p['major_stars']) or '空宫'
        print('%s(%s%s): %s' % (p['name'], p['heavenly_stem'], p['earthly_branch'], stars))

print()
print('=== 验收3: 生年四化 ===')
for m in pl['year_mutagens']:
    print('%s%s @ %s(%s)' % (m['star'], m['mutagen'], m['palace'], m['branch']))

print()
print('=== 验收4: 流年/大限/流月落宫 (target 2026) ===')
horo = get_horoscope(1998, 6, 15, 10, '男', 2026)
print('流年落宫:', horo['yearly_palace'], '| 大限落宫:', horo['decadal_palace'], '| 流月落宫:', horo['monthly_palace'])
print('流年十二宫前6:', [yp['name'] for yp in horo['yearly_palaces'][:6]])
print('流曜:', horo['liuyao'])

print()
print('=== 验收5: 格局冒烟 ===')
plate = plate_to_dict(pl, {})
pats = detect_patterns(plate)
print('格局数:', len(pats), '|', '、'.join(p['name'] for p in pats[:10]))
