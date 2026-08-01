#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""紫微斗数系统化测试 — 排盘 · 格局 · 流年 · 流曜 · API 端点"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from ziwei_calculator import (
    ziwei_paipan, plate_to_dict, get_horoscope,
    calculate_liuyao, detect_patterns,
    hour_to_shichen_index, PALACE_NAMES_CN, BRANCH_GRID,
)

# ── 颜色 ──
G = '\033[92m'; R = '\033[91m'; Y = '\033[93m'; N = '\033[0m'; B = '\033[1m'

pass_count = 0; fail_count = 0; error_count = 0; total = 0

def check(name, condition, detail=''):
    global pass_count, fail_count, error_count, total
    total += 1
    if condition:
        pass_count += 1; print(f'{G}✅{N} [{name}] {detail}')
    else:
        fail_count += 1; print(f'{R}❌{N} [{name}] {detail}')

def test_group(name, tests):
    global error_count
    print(f'\n{B}{name}{N}')
    for t_name, fn in tests:
        try: fn(t_name)
        except Exception as e:
            error_count += 1; print(f'{R}💥{N} [{t_name}] {e}')

# ══════════════════════════════════════════════
def run():
    global pass_count, fail_count, error_count, total

    # ── 基础排盘 ──
    test_group('基础排盘', [
        ('1991-08-15 丑时 男', lambda n: _t_paipan(n, 1991,8,15,1,0,'男', '金四局', 12, 4)),
        ('2005-08-19 丑时 男', lambda n: _t_paipan(n, 2005,8,19,1,35,'男', None, 12, 4)),
        ('2000-01-01 卯时 男', lambda n: _t_paipan(n, 2000,1,1,6,0,'男', None, 12, 4)),
        ('1984-02-02 午时 男', lambda n: _t_paipan(n, 1984,2,2,12,0,'男', None, 12, 4)),
        ('性别 女', lambda n: _t_paipan(n, 1991,8,15,1,0,'女', None, 12, 4)),
    ])

    # ── 时辰映射 ──
    test_group('时辰映射', [
        ('hour  1→丑时', lambda n: check(n, hour_to_shichen_index(1)==1)),
        ('hour 12→午时', lambda n: check(n, hour_to_shichen_index(12)==6)),
        ('hour 23→夜子', lambda n: check(n, hour_to_shichen_index(23)==0)),
        ('hour  0→早子', lambda n: check(n, hour_to_shichen_index(0)==0)),
    ])

    # ── 星曜结构 ──
    data = ziwei_paipan(1991,8,15,1,0,'男')
    plate = plate_to_dict(data, {'birth_datetime':'1991-8-15 01:00','gender':'男'})
    palaces = plate['palaces']

    test_group('星曜结构', [
        ('major_stars 是 dict 列表', lambda n: check(n, all(isinstance(s,dict) and 'name' in s for p in palaces for s in p['major_stars']))),
        ('brightness 字段存在', lambda n: check(n, any(s.get('brightness') for p in palaces for s in p['major_stars']))),
        ('mutagen 字段存在', lambda n: check(n, any(s.get('mutagen') for p in palaces for s in p['major_stars']) or any(s.get('mutagen') for p in palaces for s in p['minor_stars']))),
        ('type 字段存在', lambda n: check(n, all('type' in s for p in palaces for s in p['major_stars']+p['minor_stars']))),
        ('css 字段存在', lambda n: check(n, all('css' in s for p in palaces for s in p['major_stars']+p['minor_stars']))),
    ])

    # ── 宫位 ═══
    test_group('十二宫', [
        ('宫数=12', lambda n: check(n, len(palaces)==12)),
        ('命宫/身宫 非空', lambda n: check(n, plate['soul_palace'] and plate['body_palace'])),
        ('五行局 非空', lambda n: check(n, plate['five_elements_class'])),
        ('每宫有 dizhi', lambda n: check(n, all(p['dizhi'] for p in palaces))),
        ('每宫有 decadal_range', lambda n: check(n, all('decadal_range' in p for p in palaces))),
        ('命宫标记正确', lambda n: check(n, any('命宫' in p.get('tags',[]) for p in palaces))),
        ('身宫标记正确', lambda n: check(n, any('身宫' in p.get('tags',[]) for p in palaces))),
        ('grid_row/col 有效', lambda n: check(n, all(1<=p['grid_row']<=4 and 1<=p['grid_col']<=4 for p in palaces))),
    ])

    # ── 格局 ═══
    test_group('格局判读', [
        ('1991-8-15 有≥1格局', lambda n: check(n, len(detect_patterns(plate))>=1)),
        ('2005-8-19 有≥1格局', lambda n: _t_patterns(n, 2005,8,19,1,35,'男')),
        ('1984-2-2 有≥1格局', lambda n: _t_patterns(n, 1984,2,2,12,0,'男')),
        ('格局含 name+level+desc', lambda n: _t_pattern_fields(n, plate)),
    ])

    # ── 四化 ──
    ym = plate['year_mutagens']
    test_group('生年四化', [
        ('四化数=4', lambda n: check(n, len(ym)==4)),
        ('含 star+mutagen+palace+branch', lambda n: check(n, all(all(k in m for k in ['star','mutagen','palace','branch']) for m in ym))),
        ('化禄/权/科/忌 齐全', lambda n: check(n, len(set(m['mutagen'] for m in ym))==4)),
    ])

    # ── 流年 ═══
    horo = get_horoscope(1991,8,15,1,'男',2025)
    test_group('流年盘', [
        ('yearly_gz 正确', lambda n: check(n, horo['yearly_gz'])),
        ('yearly_palace 有效', lambda n: check(n, horo['yearly_palace'])),
        ('decadal_gz 有效', lambda n: check(n, horo['decadal_gz'])),
        ('liuyao 有数据', lambda n: check(n, len(horo['liuyao'])>=8)),
    ])

    # ── 流曜 ═══
    liuyao = calculate_liuyao('甲','辰',palaces)
    test_group('流曜计算', [
        ('10种流曜', lambda n: check(n, len(liuyao)==10)),
        ('流禄 有值', lambda n: check(n, '流禄' in liuyao and liuyao['流禄'])),
        ('流羊 有值', lambda n: check(n, '流羊' in liuyao and liuyao['流羊'])),
        ('流昌 有值', lambda n: check(n, '流昌' in liuyao and liuyao['流昌'])),
        ('流马 有值', lambda n: check(n, '流马' in liuyao and liuyao['流马'])),
    ])

    # ── API 端点 ──
    with app.test_client() as c:

        test_group('API: /api/ziwei/paipan', [
            ('正常排盘', lambda n: _t_api_paipan(n, c, {'year':1991,'month':8,'day':15,'hour':1,'gender':'男'})),
            ('缺少字段→400', lambda n: check(n, c.post('/api/ziwei/paipan',json={'year':1991}).status_code==400)),
            ('性别错误→400', lambda n: check(n, c.post('/api/ziwei/paipan',json={'year':1991,'month':8,'day':15,'hour':1,'gender':'x'}).status_code==400)),
            ('含 patterns', lambda n: check(n, 'patterns' in c.post('/api/ziwei/paipan',json={'year':1991,'month':8,'day':15,'hour':1,'gender':'男'}).get_json())),
        ])

        test_group('API: /api/ziwei/horoscope', [
            ('正常流年', lambda n: _t_api_horo(n, c, {'year':1991,'month':8,'day':15,'hour':1,'gender':'男','target_year':2025})),
            ('含 liuyao', lambda n: check(n, len(c.post('/api/ziwei/horoscope',json={'year':1991,'month':8,'day':15,'hour':1,'gender':'男','target_year':2025}).get_json().get('liuyao',{}))>=8)),
        ])

        test_group('API: /api/ziwei/analyze', [
            ('密码校验→403', lambda n: check(n, c.post('/api/ziwei/analyze',json={'plate':{}}).status_code==403)),
            ('缺plate→403(密码检查在前)', lambda n: check(n, c.post('/api/ziwei/analyze',json={}).status_code==403)),
        ])

    # ── 边界 ──
    test_group('边界用例', [
        ('1900年 不崩溃', lambda n: _t_edge(n, 1900,6,15,12,0,'男')),
        ('2100年 不崩溃', lambda n: _t_edge(n, 2100,1,1,0,0,'女')),
        ('农历排盘', lambda n: _t_lunar(n)),
        ('cache_key 不崩溃', lambda n: _t_cache_key(n)),
    ])

    # ── 结果 ──
    print(f'\n{"="*60}')
    print(f'{B}结果：{G}{pass_count} 通过{N} / {R}{fail_count} 失败{N} / {Y}{error_count} 错误{N} (共 {total})')
    pct = pass_count*100//total if total else 0
    bar = '█'*(pct//4)+'░'*(25-pct//4)
    print(f'{bar} {pct}%')
    return fail_count == 0 and error_count == 0

# ── 辅助 ──
def _t_paipan(name, y,m,d,h,mi,g, fec_exp, pal_exp, ym_exp):
    data = ziwei_paipan(y,m,d,h,mi,g)
    p = plate_to_dict(data, {})
    ok = True
    if fec_exp: ok = ok and p['five_elements_class']==fec_exp
    ok = ok and len(p['palaces'])==pal_exp
    ok = ok and len(p['year_mutagens'])==ym_exp
    stars = [s['name'] for s in p['palaces'][0]['major_stars']] if p['palaces'][0]['major_stars'] else ['空宫']
    check(name, ok, f'{p["five_elements_class"]} 命{p["soul_palace"]} 身{p["body_palace"]} P0={"/".join(stars)}')

def _t_patterns(name, y,m,d,h,mi,g):
    data = ziwei_paipan(y,m,d,h,mi,g)
    plate = plate_to_dict(data, {})
    check(name, len(detect_patterns(plate))>=1, f'{len(detect_patterns(plate))} patterns')

def _t_pattern_fields(name, plate):
    ps = detect_patterns(plate)
    ok = all('name' in p and 'level' in p and 'desc' in p for p in ps)
    check(name, ok, f'All {len(ps)} patterns have name+level+desc')

def _t_api_paipan(name, c, body):
    r = c.post('/api/ziwei/paipan', json=body)
    d = r.get_json()
    pc = len(d.get('palaces',[]))
    ok = r.status_code==200 and pc==12
    check(name, ok, f'status={r.status_code} palaces={pc}')

def _t_api_horo(name, c, body):
    r = c.post('/api/ziwei/horoscope', json=body)
    d = r.get_json()
    ygz = d.get('yearly_gz',''); yp = d.get('yearly_palace','')
    ok = r.status_code==200 and bool(ygz)
    check(name, ok, f'{ygz} year palace={yp}')

def _t_analyze_yearly(name, c):
    r = c.post('/api/ziwei/analyze/yearly', json={'year':1991,'month':8,'day':15,'hour':1,'gender':'男','target_year':2025,'password':'x'})
    check(name, r.status_code==403, 'password check')

def _t_edge(name, y,m,d,h,mi,g):
    try:
        data = ziwei_paipan(y,m,d,h,mi,g)
        p = plate_to_dict(data, {})
        ok = len(p['palaces'])==12 and len(p['year_mutagens'])==4
    except: ok = False
    check(name, ok)

def _t_lunar(name):
    try:
        data = ziwei_paipan(2023,6,15,12,0,'男',is_lunar=True)
        p = plate_to_dict(data, {})
        ok = len(p['palaces'])==12
    except: ok = False
    check(name, ok)

def _t_cache_key(name):
    from utils.cache import _make_ziwei_cache_key  # 函数在 utils/cache.py（app 无此导出）
    plate = plate_to_dict(ziwei_paipan(1991,8,15,1,0,'男'), {})
    try:
        key = _make_ziwei_cache_key(plate)
        ok = key and len(key)==16
    except: ok = False
    check(name, ok)

# ── 自检 ──
if __name__ == '__main__':
    from datetime import datetime as dt2
    print(f'紫微斗数 系统化测试 — {dt2.now().strftime("%Y-%m-%dT%H:%M:%S")}')
    print('用例数：统计中...')
    ok = run()
    sys.exit(0 if ok else 1)
