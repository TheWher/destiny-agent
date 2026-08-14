# -*- coding: utf-8 -*-
"""
diff_llm_engine_geju.py — LLM 自判格局 vs 引擎 detect_patterns 双向 diff（2026-08-14 mose 接）

用途：量化「解读说的格局」和「引擎检出的格局」之间的差距。
- 前向（误判/虚报）：文本提到引擎判无的格局名
- 反向（漏判）：引擎判有、文本没提的格局名
- 状态级接口预留：注入接通后（v2）再比文本核验状态（✅成立/⚠️受损/❌破格）vs 引擎状态

输入：JSON 文件，格式
{
  "meta": {"note": "..."},
  "cases": [
    {"id": "king-2005", "kind": "真盘", "birth": [2005, 8, 19, 1, 35, "男"], "text": "LLM 解读全文..."}
  ]
}
kind 取值：真盘 / 待确认盘 / 古籍例盘 / 构造盘（统计分层，不混桶，CLAUDE.md 数据来源标签纪律）

用法：
  python scripts/diff_llm_engine_geju.py cases.json -o docs/geju_diff_baseline_YYYYMMDD.json
  python scripts/diff_llm_engine_geju.py --demo          # 自检：合成文本冒烟测试

输出 JSON 可 diff（同一批盘注入前/注入后各跑一版，diff 即「变准了多少」）。
"""
import argparse
import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, __file__.rsplit('scripts', 1)[0] or '.')

import ziwei_calculator as z

# ── 别名 canon（与 services/ziwei_analysis.py verify 的 _GEJU_ALIAS 同源，改动两边同步）──
# 约定：canon = 去掉「格」后缀后的规范名。引擎名「杀破狼格」与文本「杀破狼」同 canon。
_GEJU_ALIAS = {
    '机月同梁': '机月同梁格', '机月格': '机月同梁格', '杀破狼': '杀破狼格',
    '紫府朝垣': '紫府朝垣格', '府相朝垣': '府相朝垣格', '火贪': '火贪格',
    '铃贪': '铃贪格', '日月并明': '日月并明格', '石中隐玉': '石中隐玉格',
    '紫微天府': '紫府同宫', '君臣庆会': '君臣庆会', '月朗天门': '月朗天门',
    '日照雷门': '日照雷门',
}

# 四化系 7 格 = 引擎铺的应事标签，非传统格局（2026-08-14 频道定：单独标「非格局类」）
# 它们永远会被 LLM 以「XX化忌在XX宫」而非格名形式表述，进漏判统计会虚高，故剔除。
_SIHUA_PAT = re.compile(r'^(命宫|命宮|夫妻宫|夫妻|财帛|財帛|官禄|官祿)(宫)?化(禄|权|忌|科)$')


def canon(name: str) -> str:
    """规范化：别名映射 + 去「格」后缀。"""
    n = _GEJU_ALIAS.get(name, name)
    return n[:-1] if n.endswith('格') else n


def is_sihua_label(name: str) -> bool:
    return bool(_SIHUA_PAT.match(name))


def engine_canon_set(plate) -> dict:
    """引擎检出 → {canon: {'name', 'level', 'status', 'breaking_hits', 'enhancer_hits'}}；四化系另分桶。
    2026-08-14 v2：消费口落地后 detect_patterns 带 geju_status/breaking_hits/enhancer_hits，
    旧引擎无 geju_status 时兜底推导（conditions.breaking 非空 → 破格，否则成立）。"""
    pats = z.detect_patterns(plate)
    real, sihua = {}, {}
    for p in pats:
        name = p.get('name', '')
        c = canon(name)
        status = p.get('geju_status') or ('破格' if p.get('conditions', {}).get('breaking') else '成立')
        info = {'name': name, 'level': p.get('level', ''), 'status': status,
                'breaking_hits': p.get('breaking_hits', []),
                'enhancer_hits': p.get('enhancer_hits', [])}
        if is_sihua_label(name):
            sihua[c] = info
        else:
            real[c] = info
    return real, sihua


def scan_text(text: str, engine_pats: dict) -> dict:
    """文本扫描 → {'mentioned': {canon: 原词}, 'false_pos': {canon: 原词}}
    复用 verify 的否定语境排除（无/未/不/非/不成/没有/不具备 前缀 6 字内）。"""
    if not text:
        return {'mentioned': {}, 'false_pos': {}}
    known = set(engine_pats) | set(_GEJU_ALIAS.keys()) | set(_GEJU_ALIAS.values())
    names = sorted(known, key=len, reverse=True)
    mentioned, false_pos = {}, {}
    seen = set()
    for gname in names:
        c = canon(gname)
        if c in seen:
            continue
        seen.add(c)
        for m in re.finditer(re.escape(gname), text):
            pre = text[max(0, m.start() - 6):m.start()]
            if any(neg in pre for neg in ('无', '未', '不', '非', '不成', '没有', '不具备')):
                continue
            if c in engine_pats:
                mentioned.setdefault(c, gname)
            else:
                false_pos.setdefault(c, gname)
            break  # 每个 canon 只记一次有无
    return {'mentioned': mentioned, 'false_pos': false_pos}


def _align_truth(info, truth_label: str) -> str:
    """真值对齐判定：ok / engine_bug / known_dispute。
    truth_label ∈ clean / breaking / reject / weakener / huizhao_only（2026-08-14 频道定）。
    - clean：引擎成立 → ok
    - breaking：引擎受损/破格 → ok（该列的必须列，只是降级）
    - reject：引擎不列 → ok（不成立直接剔除）
    - weakener：引擎成立（只减语气不降级）→ ok
    - huizhao_only：教材口径非成格 vs 引擎会照次格，预期分歧，留 harness 裁决 → known_dispute
    """
    if truth_label == 'huizhao_only':
        return 'known_dispute'
    if truth_label == 'reject':
        return 'ok' if info is None else 'engine_bug'
    if info is None:
        return 'engine_bug'  # 该有的没列（clean/breaking/weakener 都要求列出）
    if truth_label == 'clean':
        return 'ok' if info['status'] == '成立' else 'engine_bug'
    if truth_label == 'breaking':
        return 'ok' if info['status'] in ('受损', '破格') else 'engine_bug'
    if truth_label == 'weakener':
        return 'ok'
    return 'pending'


def diff_case(case: dict) -> dict:
    """单盘 diff → 误判（文本提了引擎判无）+ 漏判（引擎判有文本没提）+
    v2 真值列（expected={canon: truth_label}，教材口径/古籍断语真值裁决引擎与 LLM）。"""
    birth = case['birth']
    plate = z.ziwei_paipan(*birth)
    real, sihua = engine_canon_set(plate)
    scan = scan_text(case.get('text', ''), real)
    engine_canons = set(real)
    mentioned = set(scan['mentioned'])
    false_pos = set(scan['false_pos'])
    false_neg = engine_canons - mentioned
    result = {
        'id': case.get('id', ''),
        'kind': case.get('kind', '未标'),
        'birth': list(birth),
        'year_gz': plate.get('year_gz', ''),
        'engine_pats': sorted(engine_canons),
        'sihua_labels': sorted(sihua),
        'mentioned': sorted(mentioned),
        'false_pos': sorted(false_pos),
        'false_neg': sorted(false_neg),
    }
    expected = case.get('expected') or {}
    if expected:
        truth = {}
        for c0, tl in expected.items():
            c = canon(c0)  # expected 键归一：'火贪格'/'杀破狼格' 落 canon '火贪'/'杀破狼'
            info = real.get(c)
            truth[c] = {'truth': tl,
                        'engine_present': info is not None,
                        'engine_status': info['status'] if info else '',
                        'engine_level': info['level'] if info else '',
                        'llm_mentioned': c in mentioned,
                        'align': _align_truth(info, tl)}
        result['truth'] = truth
    return result


def aggregate(cases_out: list) -> dict:
    """盘型分层汇总（真盘/古籍例盘/构造盘不混桶）。真值列：truth_ok / truth_bug / truth_dispute。"""
    agg = {}
    for c in cases_out:
        k = c['kind']
        b = agg.setdefault(k, {'total': 0, 'fp': [], 'fn': [],
                               'truth_total': 0, 'truth_ok': 0, 'truth_bug': 0,
                               'truth_dispute': 0, 'truth_detail': []})
        b['total'] += 1
        b['fp'] += c['false_pos']
        b['fn'] += c['false_neg']
        for c2, t in (c.get('truth') or {}).items():
            b['truth_total'] += 1
            if t['align'] == 'ok':
                b['truth_ok'] += 1
            elif t['align'] == 'engine_bug':
                b['truth_bug'] += 1
                b['truth_detail'].append(f"{c2}:{t['truth']}(引擎{t['engine_status'] or '不列'})")
            elif t['align'] == 'known_dispute':
                b['truth_dispute'] += 1
                b['truth_detail'].append(f"分歧:{c2}:{t['truth']}(引擎{t['engine_status'] or '不列'})")
    for b in agg.values():
        b['fp'] = sorted(set(b['fp']))
        b['fn'] = sorted(set(b['fn']))
    return agg


def demo_cases() -> dict:
    """自检样例：文本 diff 用合成文本，真值列用构造盘（火贪 clean/reject、杀破狼 breaking）。"""
    return {
        'meta': {'note': '自检 demo：文本为合成，非真实 LLM 输出；构造盘真值来自 geju_trigger_pans_v2 清单标签'},
        'cases': [
            {'id': 'demo-king', 'kind': '真盘', 'birth': [2005, 8, 19, 1, 35, '男'],
             'text': '此盘命坐未宫，太阳卯庙太阴亥庙，日月并明成立，明珠出海亦为古诀专名，财官双美。'},
            {'id': 'demo-guangxu', 'kind': '构造盘', 'birth': [2005, 1, 15, 0, 30, '男'],
             'text': '命丑日月同宫，日月同臨格成立，但此盘并无日月并明。'},
            {'id': 'demo-clean', 'kind': '构造盘', 'birth': [1941, 2, 1, 4, 0, '男'],
             'text': '贪狼同宫火星，火贪格成立，爆发力强。', 'expected': {'火贪格': 'clean'}},
            {'id': 'demo-reject', 'kind': '构造盘', 'birth': [1941, 1, 13, 14, 0, '男'],
             'text': '此盘火贪同宫见羊陀，不构成火贪格。', 'expected': {'火贪格': 'reject'}},
            {'id': 'demo-breaking', 'kind': '构造盘', 'birth': [1941, 1, 1, 18, 0, '男'],
             'text': '杀破狼格三方齐聚，然坐空劫受损。', 'expected': {'杀破狼格': 'breaking'}},
            {'id': 'demo-huizhao-dispute', 'kind': '构造盘', 'birth': [1941, 1, 27, 16, 0, '男'],
             'text': '', 'expected': {'铃贪格': 'huizhao_only'}},  # 2026-08-14 分歧样本：教材口径不成立 vs 引擎会照次格成立，留裁决
        ],
    }


def run(cases: dict, out_path: str = None) -> list:
    out = []
    for case in cases.get('cases', []):
        out.append(diff_case(case))
    agg = aggregate(out)
    result = {'meta': cases.get('meta', {}), 'cases': out, 'aggregate': agg,
              'note': 'v2：name 级双向 diff + 真值列（expected=教材口径/古籍断语标签，裁决引擎与 LLM）；状态级文本提取留待注入后'}
    if out_path:
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"written: {out_path}")
    for c in out:
        t = ''
        if c.get('truth'):
            t = ' 真值=' + ','.join(f"{k}:{v['align']}" for k, v in c['truth'].items())
        print(f"[{c['kind']}] {c['id']} 引擎={c['engine_pats']} 误判={c['false_pos']} 漏判={c['false_neg']}{t}")
    print(json.dumps(agg, ensure_ascii=False, indent=2))
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('cases', nargs='?', help='cases JSON 路径')
    ap.add_argument('-o', '--out', default=None, help='输出 JSON 路径')
    ap.add_argument('--demo', action='store_true', help='跑自检样例')
    args = ap.parse_args()
    if args.demo:
        run(demo_cases(), args.out)
    elif args.cases:
        with open(args.cases, encoding='utf-8') as f:
            run(json.load(f), args.out)
    else:
        ap.print_help()
        sys.exit(1)
