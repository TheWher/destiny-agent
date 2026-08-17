# -*- coding: utf-8 -*-
"""
find_geju_trigger_pans.py — 破格触发盘构造清单（2026-08-14 hanako）

目的：给 diff harness / 破格表验证提供命中 5 个已标格局（火贪/铃贪/君臣庆会/杀破狼/机月同梁）的构造盘。
盘型 = 构造盘（推导/合成，无现实锚，验规则自洽；库纪律：构造盘全过验的是规则自洽，规则跟现实对不对得上锚点是真盘）。

扫描空间：1941-2000（60 年，60 甲子全覆盖）× 12 月 × 28 日 × 12 时辰。
成本：iztro paipan ~9ms/盘（实测），全量 ~36 分钟；本脚本抽样早退：
- 每个目标格局收满 quota（默认 4）即停该格
- 全部收满或到 scan_cap（默认 30000）即整体停止
- 每次打印进度，防假死

输出：docs/geju_trigger_pans_v1.md（清单）+ stdout 摘要。
用法：python scripts/find_geju_trigger_pans.py
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, __file__.rsplit('scripts', 1)[0] or '.')

import ziwei_calculator as z

ZHI = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥']
SHA_HARD = {'擎羊', '陀罗', '火星', '铃星'}
SHA_KONG = {'地空', '地劫'}

TARGETS = ['火贪格', '铃贪格', '君臣庆会', '杀破狼格', '机月同梁格']
# 类别配额：clean/breaking 各 2，reject/weakener/会照档 各 1（火贪铃贪适用全部，其余格只用 clean/breaking）
QUOTA = {'clean': 2, 'breaking': 2, 'reject': 1, 'weakener': 1, 'huizhao_only': 1}
SCAN_CAP = 20000


def _names(p):
    return [s['name'] for s in p.get('major_stars', [])] + [s['name'] for s in p.get('minor_stars', [])]


def _star_palace(palaces, name):
    for p in palaces:
        if name in _names(p):
            return p
    return None


def _brightness(p, name):
    for s in p.get('major_stars', []) + p.get('minor_stars', []):
        if s.get('name') == name:
            return s.get('brightness', '')
    return ''


def _sf_branches(mb):
    i = ZHI.index(mb)
    return {ZHI[i], ZHI[(i + 4) % 12], ZHI[(i + 8) % 12], ZHI[(i + 6) % 12]}


def _sf_names(palaces, mb):
    out = set()
    for p in palaces:
        if p.get('earthly_branch', '') in _sf_branches(mb):
            out |= set(_names(p))
    return out


def _sf_ji(palaces, mb):
    """三方四正是否含化忌（mutagen 原始值 '忌'）"""
    for p in palaces:
        if p.get('earthly_branch', '') in _sf_branches(mb):
            for m in p.get('mutagens', []):
                if m.get('mutagen') in ('忌', '化忌'):
                    return True
    return False


def _done(hits_by_cls):
    return all(len(hits_by_cls.get(c, [])) >= q for c, q in QUOTA.items())


def _sf_lu_quan(palaces, mb):
    """三方四正是否含化禄/化权（mutagen 原始值 '禄'/'权'）"""
    for p in palaces:
        if p.get('earthly_branch', '') in _sf_branches(mb):
            for m in p.get('mutagens', []):
                if m.get('mutagen') in ('禄', '化禄', '权', '化权'):
                    return True
    return False


def features(palaces, mb):
    """提取 5 个已标格局的判定特征指纹"""
    sf = _sf_names(palaces, mb)
    tan = _star_palace(palaces, '贪狼')
    huoxing = _star_palace(palaces, '火星')
    lingxing = _star_palace(palaces, '铃星')
    ming = next((p for p in palaces if '命宫' in p.get('tags', [])), {})
    ming_names = set(_names(ming))
    return {
        'ming_branch': mb,
        'ming_names': sorted(ming_names),
        'tan_bright': _brightness(tan, '贪狼') if tan else '',
        'tan_with_ziwei': '紫微' in set(_names(tan)) if tan else False,
        'tan_with_lianzhen': '廉贞' in set(_names(tan)) if tan else False,
        'huoxing_same_tan': bool(huoxing and tan and huoxing.get('earthly_branch') == tan.get('earthly_branch')),
        'lingxing_same_tan': bool(lingxing and tan and lingxing.get('earthly_branch') == tan.get('earthly_branch')),
        'yangtuo_with_huoxing': bool(huoxing and (set(_names(huoxing)) & {'擎羊', '陀罗'})),
        'yangtuo_with_lingxing': bool(lingxing and (set(_names(lingxing)) & {'擎羊', '陀罗'})),
        'sf_sha_count': sum(1 for s in sf if s in SHA_HARD),
        'sf_has_yangtuo': bool(sf & {'擎羊', '陀罗'}),
        'sf_has_ji': _sf_ji(palaces, mb),
        'sf_kongjie': bool(sf & SHA_KONG),
        'sf_tianxing': '天刑' in sf,
        'sf_zuoyou': len(sf & {'左辅', '右弼'}),
        'sf_hualu_quan': _sf_lu_quan(palaces, mb),
    }


def classify_huotan(f, is_ling):
    """按标注 JSON 的火贪/铃贪条目给盘分类（2026-08-14 v2：reject 需同宫前提；不同宫归会照档）"""
    sha_with = 'yangtuo_with_lingxing' if is_ling else 'yangtuo_with_huoxing'
    same = 'lingxing_same_tan' if is_ling else 'huoxing_same_tan'
    if f[sha_with] and f[same]:
        return 'reject(羊陀与火/铃同宫)'
    if not f[same]:
        return 'huizhao_only(教材口径非成格)'
    if f['sf_kongjie'] and (f['sf_tianxing'] or f['sf_has_ji']):
        return 'breaking(空劫刑忌并见)'
    if f['sf_has_yangtuo'] or f['sf_has_ji']:
        return 'breaking(三方羊陀/化忌)'
    if f['tan_with_ziwei'] or f['tan_with_lianzhen']:
        return 'weakener(紫贪/廉贪同宫)'
    if f['sf_kongjie']:
        return 'weakener(单见空劫,disputed)'
    if f['tan_bright'] in ('庙', '旺'):
        return 'clean(同宫+贪狼庙旺)'
    return 'clean(其他)'


def main():
    hits = {t: {} for t in TARGETS}  # 格局 -> {类别: [盘]}
    hit_total = {t: 0 for t in TARGETS}
    pan_total = 0
    huotan_tonggong = 0
    huotan_huizhao_only = 0

    hours = list(range(0, 24, 2))
    for year in range(1941, 2001):
        for month in range(1, 13):
            for day in range(1, 29):
                for hour in hours:
                    if all(_done(hits[t]) for t in TARGETS):
                        break
                    if pan_total >= SCAN_CAP:
                        break
                    pan_total += 1
                    try:
                        plate = z.ziwei_paipan(year, month, day, hour, 0, '男')
                    except Exception:
                        continue
                    pats = z.detect_patterns(plate)
                    pat_names = {p['name'] for p in pats}
                    mb = next((p for p in plate['palaces'] if '命宫' in p.get('tags', [])), {}).get('earthly_branch', '')
                    f = features(plate['palaces'], mb)
                    for t in TARGETS:
                        p_entry = next((p for p in pats if p['name'] == t), None)
                        if p_entry is None:
                            continue
                        # 杀破狼/机月同梁有「不全」变体（conditions=None），不入破格表清单
                        if t in ('杀破狼格', '机月同梁格') and not p_entry.get('conditions'):
                            continue
                        hit_total[t] += 1
                        rec = {
                            'birth': (year, month, day, hour),
                            'level': p_entry['level'],
                            'breaking': p_entry.get('conditions', {}).get('breaking', []),
                            'engine_status': p_entry.get('geju_status', ''),
                            'engine_brk_hits': p_entry.get('breaking_hits', []),
                            'engine_wkn_hits': p_entry.get('weakener_hits', []),
                            'features': f,
                            'cls': '',
                        }
                        if t == '火贪格':
                            rec['cls'] = classify_huotan(f, False)
                            if f['huoxing_same_tan']:
                                huotan_tonggong += 1
                            else:
                                huotan_huizhao_only += 1
                        elif t == '铃贪格':
                            rec['cls'] = classify_huotan(f, True)
                        elif t == '君臣庆会':
                            rec['cls'] = 'breaking(命坐煞/煞重)' if rec['breaking'] else 'clean(上吉)'
                        elif t == '杀破狼格':
                            rec['cls'] = 'breaking(%s)' % '、'.join(rec['breaking']) if rec['breaking'] else 'clean'
                        elif t == '机月同梁格':
                            rec['cls'] = 'breaking(%s)' % '、'.join(rec['breaking']) if rec['breaking'] else 'clean(上吉)'
                        cls = rec['cls']
                        bucket = 'clean' if cls.startswith('clean') else ('breaking' if cls.startswith('breaking') else ('reject' if cls.startswith('reject') else ('weakener' if cls.startswith('weakener') else 'huizhao_only')))
                        if bucket in QUOTA and len(hits[t].setdefault(bucket, [])) < QUOTA[bucket]:
                            hits[t][bucket].append(rec)
                else:
                    continue
                break  # hour loop done with quota
            else:
                continue
            break  # day loop done with quota
        else:
            continue
        break  # month loop done with quota

    # ---- 输出清单 ----
    lines = []
    lines.append('# 破格触发盘构造清单 v3（2026-08-14 hanako）')
    lines.append('')
    lines.append('盘型=构造盘（验规则自洽）。扫描 %d 盘，火贪命中 %d（同宫 %d / 仅会照 %d）。' % (pan_total, hit_total['火贪格'], huotan_tonggong, huotan_huizhao_only))
    lines.append('对照列：我的教材口径标签 vs 引擎新 geju_status（成立/受损/破格/不成立），供 expected 真值列与 diff harness 裁决。')
    lines.append('')
    for t in TARGETS:
        lines.append('## %s（命中 %d 盘）' % (t, hit_total[t]))
        for bucket in ['clean', 'breaking', 'reject', 'weakener', 'huizhao_only']:
            for r in hits[t].get(bucket, []):
                y, m, d, h = r['birth']
                f = r['features']
                lines.append('- **%s** | %04d-%02d-%02d %02d时 | 命%s | 引擎level=%s breaking=%s | 引擎状态=%s（%s%s）' % (
                    r['cls'], y, m, d, h, f['ming_branch'], r['level'], r['breaking'],
                    r['engine_status'], r['engine_brk_hits'], ('弱化:' + ','.join(r['engine_wkn_hits']) if r['engine_wkn_hits'] else '')))
                lines.append('  - 贪狼%s | 火同贪=%s 铃同贪=%s | 三方硬煞%d 羊陀=%s 化忌=%s 空劫=%s 天刑=%s | 紫贪=%s 廉贪=%s' % (
                    f['tan_bright'], f['huoxing_same_tan'], f['lingxing_same_tan'],
                    f['sf_sha_count'], f['sf_has_yangtuo'], f['sf_has_ji'], f['sf_kongjie'], f['sf_tianxing'],
                    f['tan_with_ziwei'], f['tan_with_lianzhen']))
    lines.append('')
    lines.append('## 说明')
    lines.append('- 引擎当前不消费破格表：reject 型盘（羊陀与火/铃同宫）引擎仍报火贪格，注入后应剔除，是 diff harness 的现成对照样本')
    lines.append('- 引擎火贪/铃贪判定含「会照」分支，教材（陆斌兆/王亭之）口径为同宫庙旺；仅会照盘是潜在误判样本，基线 diff 重点关注')
    lines.append('- 构造盘生辰为合成数据，仅供规则验证，禁止当真人命例引用')
    out = '\n'.join(lines) + '\n'
    with open('docs/geju_trigger_pans_v3.md', 'w', encoding='utf-8') as fp:
        fp.write(out)
    print(out)
    print('== done: %d pans scanned' % pan_total)


if __name__ == '__main__':
    main()
