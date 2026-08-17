# -*- coding: utf-8 -*-
"""
find_geju_nonming_pans.py — 非命宫格局构造盘清单 v1（2026-08-17 hanako）

目的：给「注入格式加 [宫位] 锚点」的疗效对照补样本。病根（mose 定）=
LLM 格局词汇被「命宫中心」绑架：只认命坐星格局，非命宫成格的格局（财帛宫铃贪、
三方分散的杀破狼、辅弼拱照的君臣庆会）要么当煞星描述、要么不叫名。
26 盘里真核心盘只有 lt-brk-2 / jc-brk-2 两盘，疗效样本太薄，这里补 11 盘。

筛选条件（成格锚点不在命宫）：
- 铃贪/火贪：贪狼在三方他宫（财帛/官禄/迁移）与火/铃同宫，非命宫坐贪狼
- 君臣庆会：紫微坐命 + 左辅右弼在非命宫位（三方他宫/夹宫）
- 杀破狼：命宫坐三主星之一，另两星在财帛/官禄/迁移（报单星不报格场景）
- 府相朝垣：天府天相分守命三方，命宫非天府天相
- 机月同梁：命宫坐四星之一，其余散在各方

类别按引擎 geju_status 映射：成立=clean、破格=breaking（构造盘验规则自洽，
expected 给 harness 真值列裁决用）。text 留空待韩湘生跑 LLM 填充。

输出：docs/geju_trigger_pans_v4_nonming.md + docs/geju_expected_cases_v2_nm.json
用法：python scripts/find_geju_nonming_pans.py
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, __file__.rsplit('scripts', 1)[0] or '.')

import json
import ziwei_calculator as z

# 已存在的 26 盘（geju_expected_cases_v1.json）排除，避免重复
EXISTING_BIRTHS = set()

# 目标：{(格局名, 类别): 配额}
QUOTA = {
    ('铃贪格', 'clean'): 2,
    ('铃贪格', 'breaking'): 1,
    ('火贪格', 'clean'): 1,
    ('火贪格', 'breaking'): 1,
    ('君臣庆会', 'clean'): 1,
    ('君臣庆会', 'breaking'): 1,
    ('杀破狼格', 'clean'): 1,
    ('杀破狼格', 'breaking'): 1,
    ('府相朝垣', 'clean'): 1,
    ('机月同梁格', 'clean'): 1,
}
SCAN_CAP = 25000


def _names(p):
    return [s['name'] for s in p.get('major_stars', [])] + [s['name'] for s in p.get('minor_stars', [])]


def _find_star(palaces, name):
    for p in palaces:
        if name in _names(p):
            return p
    return None


def is_nonming(pat, palaces, ming_name):
    """判定格局成格锚点不在命宫。ming_name 可能含全角/半角宮，统一过滤。"""
    pname = pat.get('palace') or ''
    if not pname:
        return False
    name = pat['name']
    ming_short = ming_name[0]  # '命'
    if name in ('铃贪格', '火贪格'):
        # palace 形如「贪狼财帛宫同宫铃星」：贪狼所在宫 != 命宫
        tan_p = _find_star(palaces, '贪狼')
        return bool(tan_p and tan_p.get('name', '').startswith(ming_short) is False
                    and pat.get('palace') and '同宫' in pat['palace'])
    if name == '君臣庆会':
        # 紫微在命宫（必要条件），左右弼位置非命宫即算非命宫锚
        zy = _find_star(palaces, '紫微')
        ming = next(p for p in palaces if p.get('name', '').startswith(ming_short))
        if not zy:
            return False
        return zy.get('name', '') == ming.get('name', '')
    if name == '杀破狼格':
        # palace 形如「七杀在命宫、破军在官禄宫、贪狼在财帛宫」：
        # 最有价值样本 = 命宫不坐三主星（==0，LLM 完全不报）；其次命坐其一（==1，报单星不报格）
        parts = pname.split('、')
        ming_cnt = sum(1 for s in parts if s.split('在')[-1].startswith(ming_short))
        return ming_cnt <= 1
    if name == '府相朝垣':
        tf = _find_star(palaces, '天府')
        tx = _find_star(palaces, '天相')
        return bool(tf and tx and not tf.get('name', '').startswith(ming_short)
                    and not tx.get('name', '').startswith(ming_short))
    if name == '机月同梁格':
        # 同杀破狼：命宫不坐四星或坐其一都收（坐其一=报单星不报格场景）
        parts = pname.split('、')
        ming_cnt = sum(1 for s in parts if s.split('在')[-1].startswith(ming_short))
        return ming_cnt <= 1
    return False


def _status_bucket(pat):
    st = pat.get('geju_status', '')
    return {'成立': 'clean', '破格': 'breaking', '受损': 'weakener', '不成立': 'reject'}.get(st, 'clean')


def main():
    # 载入已有 26 盘 birth 排除
    try:
        existing = json.load(open('docs/geju_expected_cases_v1.json', encoding='utf-8'))
        for c in existing['cases']:
            b = c['birth']
            EXISTING_BIRTHS.add((b[0], b[1], b[2], b[3]))
    except FileNotFoundError:
        pass

    hits = {k: [] for k in QUOTA}
    total = 0

    hours = list(range(0, 24, 2))
    last_progress = [0]
    for year in range(1941, 2001):
        for month in range(1, 13):
            for day in range(1, 29):
                for hour in hours:
                    if all(len(hits[k]) >= q for k, q in QUOTA.items()):
                        break
                    if total >= SCAN_CAP:
                        break
                    total += 1
                    if total - last_progress[0] >= 5000:
                        got = sum(len(v) for v in hits.values())
                        print('scanned %d, got %d cases...' % (total, got), flush=True)
                        last_progress[0] = total
                    if (year, month, day, hour) in EXISTING_BIRTHS:
                        continue
                    try:
                        plate = z.ziwei_paipan(year, month, day, hour, 0, '男')
                    except Exception:
                        continue
                    pats = z.detect_patterns(plate)
                    ming = next((p for p in plate['palaces'] if '命宫' in p.get('tags', [])), {})
                    ming_name = ming.get('name', '命宮')
                    for t in pats:
                        # v3 纪律：杀破狼/机月同梁的「不全」变体（conditions=None）不入破格表清单
                        if t['name'] in ('杀破狼格', '机月同梁格') and not t.get('conditions'):
                            continue
                        key = (t['name'], _status_bucket(t))
                        if key not in QUOTA:
                            continue
                        if len(hits[key]) >= QUOTA[key]:
                            continue
                        if not is_nonming(t, plate['palaces'], ming_name):
                            continue
                        # 同格同 bucket 内保证宫位多样性（财帛/迁移各一之类）
                        pal = t.get('palace') or ''
                        if any(h['palace'] == pal for h in hits[key]):
                            continue
                        hits[key].append({
                            'birth': (year, month, day, hour),
                            'level': t.get('level'),
                            'status': t.get('geju_status'),
                            'palace': t.get('palace'),
                            'brk_hits': t.get('breaking_hits', []),
                            'ming_stars': [s['name'] for s in ming.get('major_stars', [])]
                                          + [s['name'] for s in ming.get('minor_stars', [])],
                            'ming_branch': ming.get('earthly_branch', ''),
                        })
                        if len(hits[key]) >= QUOTA[key]:
                            pass  # 继续扫其他 key

    # ---- 输出 md 清单 ----
    lines = ['# 非命宫格局构造盘 v1（2026-08-17 hanako）', '']
    lines.append('病根：LLM 格局词汇被「命宫中心」绑架（mose 定）。样本=成格锚点不在命宫的盘，')
    lines.append('用于「注入格式加 [宫位] 锚点」疗效对照。构造盘，验规则自洽，禁止当真人命例。')
    lines.append('')
    lines.append('扫描 %d 盘。类别=引擎 geju_status 映射（成立=clean/破格=breaking）。' % total)
    lines.append('')
    for (pat, bucket), recs in hits.items():
        lines.append('## %s %s（%d 盘）' % (pat, bucket, len(recs)))
        for r in recs:
            y, m, d, h = r['birth']
            lines.append('- %04d-%02d-%02d %02d时 | 命%s %s | %s（%s）| %s' % (
                y, m, d, h, r['ming_branch'], ','.join(r['ming_stars']),
                r['palace'], r['level'], r['brk_hits']))
    lines.append('')
    out = '\n'.join(lines) + '\n'
    with open('docs/geju_trigger_pans_v4_nonming.md', 'w', encoding='utf-8') as fp:
        fp.write(out)

    # ---- 输出 expected JSON（text 留空） ----
    cases = []
    for (pat, bucket), recs in hits.items():
        for i, r in enumerate(recs, 1):
            y, m, d, h = r['birth']
            cases.append({
                'id': 'nm-%s-%s-%d' % (pat.replace('格', ''), bucket, i),
                'kind': '构造盘',
                'birth': [y, m, d, h, 0, '男'],
                'text': '',
                'expected': {pat: bucket},
            })
    doc = {
        'meta': {
            'note': '非命宫格局 expected 真值清单 v1（2026-08-17 hanako 建，注入 [宫位] 锚点疗效对照专用）。'
                    '来源：docs/geju_trigger_pans_v4_nonming.md。text 留空待韩湘生跑 LLM 填充。'
                    'expected=引擎 geju_status 映射五类（成立=clean/破格=breaking），harness 按对齐规则裁决。'
                    'kind=构造盘（验规则自洽，禁止当真人命例）',
        },
        'cases': cases,
    }
    with open('docs/geju_expected_cases_v2_nm.json', 'w', encoding='utf-8') as fp:
        json.dump(doc, fp, ensure_ascii=False, indent=1)
    print(out)
    print('== done: %d pans scanned, %d cases -> docs/geju_expected_cases_v2_nm.json' % (total, len(cases)))


if __name__ == '__main__':
    main()
