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

# ── v2 语境过滤（2026-08-17 mose，harness v2 牵头，频道分工）──
# 病根（2026-08-17 注入后 26 盘实测）：v1 scan_text 只认格名不认语境，把「夫妻宫/身宫/
# 流年/对比/引文」语境里的非本命格局提及记成 false_pos，6 处假阳性全为此类噪声。
# 方案（韩湘生三类 + hanako 引文第四类 + 白名单兜底，频道定稿）：
#   黑名单先排除：否定 / 引文 / 非命宫宫名限定 / 流年 / 对比；
#   白名单断言兜底：无黑名单命中时，格名近旁需出现本命断言词才算格局提及，
#   否则视为描述/讨论语境排除（宁严勿宽，第一版，跑通再放宽）。
_NEG_WORDS = ('无', '未', '不', '非', '缺')
_NEG_WORDS_MULTI = ('不成', '没有', '不具备', '并非', '不算', '谈不上', '不构成', '非格', '难言', '未见', '非纯', '不置')
_PALACE_NAMES = ('命宮', '命宫', '兄弟', '夫妻', '子女', '財帛', '财帛', '疾厄',
                 '遷移', '迁移', '交友', '官祿', '官禄', '田宅', '福德', '父母', '身宫', '身宮')
_FLOW_WORDS = ('流年', '大限', '小限', '流月', '流日', '流運', '流运')
_CONTRAST_WORDS = ('不同', '不如', '区别于', '區別', '相比', '强于', '強於', '弱于',
                   '勝過', '胜过', '遜於', '逊于', '相较于', '雖不如')
_QUOTE_OPENS = ('『', '「', '"', '\"', '《')
_QUOTE_CLOSES = ('』', '」', '"', '\"', '》')
# 白名单断言词：格名前 14 字 / 后 8 字内出现 → 本命格局断言（hanako 兜底）
_ASSERT_WORDS = ('此盘', '此命盘', '此盤', '本命', '命宫坐', '命宮坐', '命宫', '命宮',
                 '成格', '正格', '入格', '为格', '成立', '构成', '構成', '形成',
                 '故为', '即为', '是为', '屬於', '属于', '典型', '正是', '此为', '此乃', '當为',
                 '判定', '判为', '判為', '引擎判', '定为', '定為', '认为', '認為',
                 '破格', '受损', '受損', '已具', '之形', '亦成', '会照', '齊會', '齐会',
                 '坐', '并美', '護持', '护持', '仍存', '亦存', '仍有')
# 正则断言（补充单字表覆盖不到的紧凑句式，如「紫微独坐子垣」的「子垣」）
_ASSERT_RE = (re.compile(r'[子丑寅卯辰巳午未申酉戌亥]垣'),)
# 转述预检：格名前出现引擎结论动词 → 引号是转述强调（如「引擎判定「火贪格❌破格」」），不按引文排除
_TRANSCRIPT_WORDS = ('判定', '判为', '判為', '引擎判', '定为', '定為', '引擎', '评为', '評為')
# 结构已述强模式：句内构成星对 + 连接词（2026-08-17 第一版仅覆盖火贪/铃贪，宁严勿宽）
_STRUCT_LINK_WORDS = ('同宫', '同度', '会照', '加会', '相会', '三合', '拱照')


def _quote_ctx(text: str, m) -> bool:
    """引文语境：格名紧贴『』包裹 = 强调式（保留）；前 10 字内出现引号开启且非紧贴 = 引文（排除）。"""
    before = text[:m.start()]
    after = text[m.end():]
    if before.endswith(_QUOTE_OPENS) and after.startswith(_QUOTE_CLOSES):
        return False  # 强调式引用格名本身，非引文
    return any(q in before[-10:] for q in _QUOTE_OPENS)


def _palace_limited(text: str, m) -> bool:
    """宫名限定：格名前 12 字内出现非命宫宫名且紧邻（宫名结束到格名 ≤8 字），
    或格名后 8 字内出现「在X宫」类后置宫名 → 描述非本命结构。"""
    pre = text[max(0, m.start() - 12):m.start()]
    post = text[m.end():m.end() + 8]
    for pn in _PALACE_NAMES:
        if pn in ('命宮', '命宫'):
            continue
        idx = pre.rfind(pn)
        if idx >= 0 and len(pre) - (idx + len(pn)) <= 8:
            return True
        if pn in post:
            return True
    return False


def scan_text(text: str, engine_pats: dict) -> dict:
    """文本扫描 v2 → {'mentioned': {canon: 原词}, 'false_pos': {canon: 原词}, 'filtered': {canon: 语境}}
    v1 只认格名不认语境；v2 黑名单（否定/引文/宫位限定/流年/对比）+ 白名单断言兜底。
    返回兼容 v1 键（mentioned/false_pos），另附 filtered 供调试。"""
    if not text:
        return {'mentioned': {}, 'false_pos': {}, 'filtered': {}}
    known = set(engine_pats) | set(_GEJU_ALIAS.keys()) | set(_GEJU_ALIAS.values())
    names = sorted(known, key=len, reverse=True)
    mentioned, false_pos, filtered = {}, {}, {}
    for gname in names:
        c = canon(gname)
        for m in re.finditer(re.escape(gname), text):
            pre2 = text[max(0, m.start() - 2):m.start()]
            pre8 = text[max(0, m.start() - 8):m.start()]
            pre14 = text[max(0, m.start() - 14):m.start()]
            post8 = text[m.end():m.end() + 8]
            # 1) 否定语境：单字否定词（无/未/不/非/缺）须紧邻格名（前 2 字内），
            #    避免误伤地支（如「坐未宫」的未）；多字否定词窗口 8 字
            if any(neg in pre2 for neg in _NEG_WORDS) or any(neg in pre8 for neg in _NEG_WORDS_MULTI):
                filtered.setdefault(c, '否定'); continue
            # 2) 引文语境：转述引擎结论的引号（引擎判定「格名」）不算引文
            if not any(tw in pre14 for tw in _TRANSCRIPT_WORDS) and _quote_ctx(text, m):
                filtered.setdefault(c, '引文'); continue
            # 3) 非命宫宫名限定
            if _palace_limited(text, m):
                filtered.setdefault(c, '宫位限定'); continue
            # 4) 流年/大限语境（前后 8 字紧邻）
            if any(fw in pre8 or fw in post8 for fw in _FLOW_WORDS):
                filtered.setdefault(c, '流年'); continue
            # 5) 对比语境（前后 8 字）
            if any(cw in pre8 or cw in post8 for cw in _CONTRAST_WORDS):
                filtered.setdefault(c, '对比'); continue
            # 6) 白名单断言兜底：无黑名单命中时，须有本命断言词（含格名前 1 字「成」特判，
            #    覆盖 baseline 紧凑句式如「同宫成火贪格」「杀破狼格亦成」）
            pre1 = text[max(0, m.start() - 1):m.start()]
            ctx14 = pre14 + post8
            if not (pre1 == '成' or any(aw in ctx14 for aw in _ASSERT_WORDS)
                    or any(rx.search(ctx14) for rx in _ASSERT_RE)):
                filtered.setdefault(c, '无断言'); continue
            # 通过全部过滤 → 记录（每个 canon 只记一次有无；
            # 2026-08-17 修：不用 seen 去重跳过，否则长名先扫被过滤后，短别名永远没机会评估）
            if c in engine_pats:
                mentioned.setdefault(c, gname)
            else:
                false_pos.setdefault(c, gname)
            break  # 每个 canon 只记一次有无
    return {'mentioned': mentioned, 'false_pos': false_pos, 'filtered': filtered}


def structure_mentioned(text: str, engine_canons: set) -> set:
    """结构已述分层（第五项，2026-08-17 频道定）：强模式——分句内构成星对 + 连接词。
    第一版仅覆盖火贪/铃贪（贪狼+火星/铃星），同宫/会照/三合等强连接才算；
    用于把漏判分成「表达层（懂了不叫名）」与「认知层（真没认出）」。"""
    found = set()
    if not text:
        return found
    for s in re.split(r'[。；\n！？!?]', text):
        if '贪狼' not in s:
            continue
        if not any(lw in s for lw in _STRUCT_LINK_WORDS):
            continue
        if '火贪' in engine_canons and '火星' in s:
            found.add('火贪')
        if '铃贪' in engine_canons and '铃星' in s:
            found.add('铃贪')
    return found


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


def _align_truth(info, truth_label: str) -> str:
    """真值对齐判定：ok / engine_bug / known_dispute。
    truth_label ∈ clean / breaking / reject / weakener / huizhao_only（2026-08-14 频道定）。
    - clean：引擎成立 → ok
    - breaking：引擎受损/破格 → ok（该列的必须列，只是降级）
    - reject：引擎不列或 status='不成立' → ok（引擎实现里 reject 盘在 detect_patterns 层带 geju_status='不成立'，routes 层才不列；不成立=该不列）
    - weakener：引擎成立（只减语气不降级）→ ok
    - huizhao_only：教材口径非成格 vs 引擎会照次格，预期分歧，留 harness 裁决 → known_dispute
    """
    if truth_label == 'huizhao_only':
        return 'known_dispute'
    if truth_label == 'reject':
        return 'ok' if (info is None or info['status'] == '不成立') else 'engine_bug'
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
    # v2（2026-08-17 频道定，韩湘生清单第 3 项）：false_neg 排除 status='不成立'（reject 盘正确不列）
    reject_canons = {c for c, info in real.items() if info['status'] == '不成立'}
    false_neg = (engine_canons - mentioned) - reject_canons
    # v2 漏判分层（2026-08-17 频道定，第五项）：结构已述（表达层）/ 结构未述（认知层）
    struct = structure_mentioned(case.get('text', ''), engine_canons)
    fn_expr = false_neg & struct
    fn_cog = false_neg - struct
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
        'fn_expression': sorted(fn_expr),
        'fn_cognitive': sorted(fn_cog),
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
        b.setdefault('fn_expression', []).extend(c.get('fn_expression') or [])
        b.setdefault('fn_cognitive', []).extend(c.get('fn_cognitive') or [])
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
        b['fn_expression'] = sorted(set(b['fn_expression']))
        b['fn_cognitive'] = sorted(set(b['fn_cognitive']))
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
