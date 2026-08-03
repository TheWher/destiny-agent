#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""紫微斗数验盘反馈聚合分析脚本

读取 feedback/ziwei/ 下所有 JSON，输出：
1. 整体命中率（区分验证触发 vs 随机抽样）
2. 各信号等级条件命中率 + 发出比例
3. 错误原因分布
4. 假阳性/假阴性分化
5. 领域级命中率
6. 盘指纹聚类分析

用法：
    python evaluate_ziwei_verify.py               # 全量分析
    python evaluate_ziwei_verify.py --verbose     # 含逐条详情
    python evaluate_ziwei_verify.py --limit 20    # 只分析最近20条
"""

import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime

FEEDBACK_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'feedback', 'ziwei')
# 会话目录：与 routes/ziwei.py 的 _SESSIONS_DIR 保持一致（routes/sessions）
SESSIONS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'routes', 'sessions')


def load_feedbacks(limit: int = None) -> list:
    """加载所有反馈 JSON"""
    if not os.path.exists(FEEDBACK_DIR):
        print(f"[错误] 反馈目录不存在: {FEEDBACK_DIR}")
        return []
    files = sorted(os.listdir(FEEDBACK_DIR), reverse=True)
    if limit:
        files = files[:limit]
    records = []
    for fn in files:
        if not fn.endswith('.json'):
            continue
        try:
            with open(os.path.join(FEEDBACK_DIR, fn), 'r', encoding='utf-8') as f:
                records.append(json.load(f))
        except Exception as e:
            print(f"[跳过] {fn}: {e}")
    return records


def classify_domain(desc: str) -> str:
    """根据事件描述推断领域"""
    d = desc.lower() if desc else ''
    keywords = {
        '学业': ['学', '考', '大学', '毕业', '读', '录取', '升学', '硕士', '博士', '研究'],
        '事业': ['工作', '换', '职', '创业', '升', '公司', '老板', '跳槽', '转行', '失业', '裁'],
        '感情': ['恋', '婚', '分手', '离婚', '感情', '桃花', '结', '男', '女', '对象', '姻'],
        '家庭': ['父母', '亲人', '家', '离世', '去世', '生病', '病', '死', '丧', '母', '父', '长辈'],
        '财富': ['钱', '财', '赚', '亏', '投资', '买房', '购', '资产', '收入'],
        '健康': ['病', '手术', '住院', '伤', '车祸', '意外', '身体'],
        '迁移': ['搬家', '出国', '留学', '移', '外地', '换城市', '离开'],
    }
    for domain, kws in keywords.items():
        for kw in kws:
            if kw in d:
                return domain
    return '其他'


def analyze(records: list, verbose: bool = False):
    if not records:
        print("没有反馈数据可分析。")
        return

    total_predictions = 0
    all_predictions = []

    # ── 按来源分离 ──
    triggered_records = []
    random_records = []
    for r in records:
        src = r.get('source', 'verification_triggered')
        if src == 'random_sample':
            random_records.append(r)
        else:
            triggered_records.append(r)
        preds = r.get('predictions', [])
        total_predictions += len(preds)
        for p in preds:
            p['_domain'] = classify_domain(p.get('desc', ''))
            p['_signal'] = p.get('signal_level', '?')
            p['_source'] = src
            p['_fingerprint'] = json.dumps(r.get('fingerprint', {}), ensure_ascii=False)
            all_predictions.append(p)

    print("=" * 60)
    print("紫微斗数验盘反馈聚合分析")
    print("=" * 60)
    print(f"反馈文件数: {len(records)}")
    print(f"  验证触发: {len(triggered_records)}")
    print(f"  随机抽样: {len(random_records)}")
    print(f"预测条数: {total_predictions}")
    print()

    # ── 1. 整体命中率 ──
    def calc_hit_rate(preds):
        if not preds:
            return 0, 0, 0, 0, 0
        correct = sum(1 for p in preds if p.get('user_label') == 'correct')
        wrong = sum(1 for p in preds if p.get('user_label') == 'wrong')
        partial = sum(1 for p in preds if p.get('user_label') == 'partially_correct')
        total = len(preds)
        hit = (correct + partial * 0.5) / total if total > 0 else 0
        return total, correct, wrong, partial, hit

    t_all, c_all, w_all, p_all, h_all = calc_hit_rate(all_predictions)
    t_tri, c_tri, w_tri, p_tri, h_tri = calc_hit_rate([p for p in all_predictions if p['_source'] == 'verification_triggered'])
    t_rnd, c_rnd, w_rnd, p_rnd, h_rnd = calc_hit_rate([p for p in all_predictions if p['_source'] == 'random_sample'])

    print("── 1. 整体命中率 ──")
    print(f"  全量: {t_all}条 | ✓{c_all} ✗{w_all} △{p_all} | 命中率 {h_all:.1%}")
    print(f"  验证触发: {t_tri}条 | ✓{c_tri} ✗{w_tri} △{p_tri} | 命中率 {h_tri:.1%}")
    print(f"  随机抽样: {t_rnd}条 | ✓{c_rnd} ✗{w_rnd} △{p_rnd} | 命中率 {h_rnd:.1%}")
    if triggered_records and random_records:
        print(f"  ⚠ 偏差: 验证触发命中率比随机抽样 {'高' if h_tri > h_rnd else '低'} {abs(h_tri - h_rnd):.1%}")
        print(f"  → 若验证触发占主导，全量命中率可能{'高估' if h_tri > h_rnd else '低估'}实际水平")
    print()

    # ── 2. 信号等级条件命中率 ──
    print("── 2. 信号等级条件命中率 ──")
    signals = defaultdict(list)
    for p in all_predictions:
        sl = p.get('_signal', '?') or '?'
        signals[sl].append(p)

    print(f"  {'等级':<6} {'条数':>4} {'占比':>6} {'✓正确':>5} {'✗错误':>5} {'△部分':>5} {'命中率':>7}")
    for level in ['S', 'A', 'B', 'C', 'D', 'E', '?']:
        preds = signals.get(level, [])
        if not preds:
            continue
        t, c, w, pa, h = calc_hit_rate(preds)
        ratio = len(preds) / total_predictions if total_predictions > 0 else 0
        print(f"  {level:<6} {len(preds):>4} {ratio:>5.0%} {c:>5} {w:>5} {pa:>5} {h:>6.0%}")

    print("  → S/A 级命中率和发出量双高 = 高质量信号")
    print("  → D/E 级命中率低但发出量也低 = 可能边界应用场景问题")
    print()

    # ── 3. 错误原因分布 ──
    print("── 3. 错误原因分布 ──")
    error_reasons = Counter()
    error_labels = {
        'time_shift': '时间偏移(>3年)',
        'type_confusion': '事件类型混淆',
        'intensity_wrong': '强度过高/过低',
        'signal_invalid': '信号不存在/错读',
        'user_memory': '用户记忆偏差',
        'other': '其他',
    }
    wrong_preds = [p for p in all_predictions if p.get('user_label') in ('wrong', 'partially_correct')]
    for p in wrong_preds:
        reason = p.get('error_reason', '') or ''
        if reason:
            error_reasons[reason] += 1
        else:
            error_reasons['未标注'] += 1

    if error_reasons:
        for reason, count in error_reasons.most_common():
            label = error_labels.get(reason, reason)
            print(f"  {label:<20} {count:>3}条 ({count/len(wrong_preds):.0%})" if wrong_preds else f"  {label:<20} {count:>3}条")
    else:
        print("  (无错误原因标注)")

    print("  → 错误原因分布决定 prompt 修改方向")
    print("  → '时间偏移'多 → 加大信号精度权重")
    print("  → '类型混淆'多 → 强化事件分类规则")
    print()

    # ── 4. 假阳性/假阴性分化 ──
    print("── 4. 错误成本矩阵 ──")
    fp = fp_rate = fn = fn_rate = 0
    for p in all_predictions:
        label = p.get('user_label', '')
        signal = p.get('_signal', '?') or '?'
        # 假阳性: Agent 说有事（S/A/B级），用户判错
        if signal in ('S', 'A', 'B') and label == 'wrong':
            fp += 1
        # 假阴性: Agent 说没事（D/E级），用户实际有事（但验盘不采集这个，只能从 wrong 里推断）
        if signal in ('D', 'E') and label == 'wrong':
            fn += 1

    total_sab = sum(1 for p in all_predictions if p.get('_signal', '?') in ('S', 'A', 'B'))
    total_de = sum(1 for p in all_predictions if p.get('_signal', '?') in ('D', 'E'))
    fp_rate = fp / total_sab if total_sab > 0 else 0
    fn_rate = fn / total_de if total_de > 0 else 0

    print(f"  假阳性 (Agent说有事,实际没发生): {fp}/{total_sab} = {fp_rate:.1%}")
    print(f"  假阴性 (Agent说没事,可能错过):    {fn}/{total_de} = {fn_rate:.1%}")
    if fp_rate > 0.3:
        print(f"  ⚠ 假阳性偏高 → Agent过度预测 → prompt中强化'信号不足时诚实跳过'")
    if fn_rate > 0.3:
        print(f"  ⚠ 假阴性偏高 → Agent漏过关键信号 → prompt中降低D/E级阈值")
    print(f"  → 感情场景可接受高假阳性(宁多提醒不可漏)")
    print(f"  → 事业/健康场景应降低假阴性(宁可多报不可错过)")
    print()

    # ── 5. 领域级命中率 ──
    print("── 5. 领域命中率 ──")
    domains = defaultdict(list)
    for p in all_predictions:
        domains[p['_domain']].append(p)

    for domain in ['学业', '事业', '感情', '家庭', '财富', '健康', '迁移', '其他']:
        preds = domains.get(domain, [])
        if not preds:
            continue
        t, c, w, pa, h = calc_hit_rate(preds)
        sig_dist = Counter(p.get('_signal', '?') for p in preds)
        top_sig = sig_dist.most_common(1)[0] if sig_dist else ('?', 0)
        error_dist = Counter(p.get('error_reason', '') for p in preds if p.get('user_label') in ('wrong', 'partially_correct'))
        top_err = error_dist.most_common(1)[0] if error_dist else ('', 0)
        print(f"  {domain:<6} {t:>3}条 | 命中率 {h:.0%} | 主信号: {top_sig[0]}({top_sig[1]}次) | 主错误: {error_labels.get(top_err[0], top_err[0] or '—')}")

    print()

    # ── 6. 盘指纹聚类 ──
    print("── 6. 盘指纹聚类 (前5类) ──")
    fp_counts = Counter(p.get('_fingerprint', '') for p in all_predictions)
    fp_hit_rates = {}
    for fp_key, count in fp_counts.most_common(10):
        fp_preds = [p for p in all_predictions if p.get('_fingerprint', '') == fp_key]
        _, _, _, _, h = calc_hit_rate(fp_preds)
        fp_hit_rates[fp_key] = (count, h)

    for fp_key, (count, hit) in sorted(fp_hit_rates.items(), key=lambda x: -x[1][0])[:5]:
        try:
            fp_obj = json.loads(fp_key)
            sihua = '、'.join(fp_obj.get('sihua', [])[:4])
            stars = '、'.join(fp_obj.get('ming_stars', []))
            lai = fp_obj.get('laiyin', '?')
            print(f"  命宫: {stars:<15} | 来因: {lai:<6} | 四化: {sihua:<30} | {count}条, 命中率 {hit:.0%}")
        except:
            print(f"  {fp_key[:60]}... | {count}条, 命中率 {hit:.0%}")

    print()

    # ── 7. 覆盖率 ──
    print("── 7. 覆盖率 ──")
    # 分子：有验盘反馈的去重 session_id 数（continue 共用同一 session_id，天然去重）
    verified_sessions = set()
    for r in records:
        sid = r.get('session_id', '')
        if sid:
            verified_sessions.add(sid)
    # 分母：会话总数（routes/sessions 下每个会话一个 JSON 文件）
    total_sessions = 0
    if os.path.isdir(SESSIONS_DIR):
        total_sessions = len([fn for fn in os.listdir(SESSIONS_DIR) if fn.endswith('.json')])
    coverage = round(len(verified_sessions) / total_sessions, 3) if total_sessions > 0 else 0.0
    print(f"  有反馈盘数(去重session): {len(verified_sessions)}")
    print(f"  会话总数: {total_sessions}")
    print(f"  覆盖率: {coverage:.1%}")
    if total_sessions == 0 and len(verified_sessions) > 0:
        print("  ⚠ 会话目录为空但有反馈记录：反馈的 session 可能已删除，或会话未落盘，覆盖率需人工核对")
    print("  → 覆盖率低 = 验盘环节没人走到（区别于解读准确率低），两层分开盯")
    print()

    print("=" * 60)
    print("分析完成。反馈积累越多，统计越可靠。")
    print(f"当前样本量: {len(all_predictions)} 条预测")
    if len(all_predictions) < 20:
        print("⚠ 样本量<20，以下结论仅供参考，不应用于修改 prompt")
    elif len(all_predictions) < 50:
        print("⚠ 样本量<50，方向性结论可用，细则需谨慎")
    print("=" * 60)

    # ── 构建聚合报告 dict ──
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total_samples": total_predictions,
        "total_records": len(records),
        "coverage": {
            "verified_sessions": len(verified_sessions),
            "total_sessions": total_sessions,
            "coverage": coverage,
        },
        "overall_accuracy": round(h_all, 3),
        "by_signal": {},
        "by_domain": {},
        "common_errors": [],
        "false_positive_rate": round(fp_rate, 3),
        "false_negative_rate": round(fn_rate, 3),
        "sample_sources": {
            "verification_triggered": len(triggered_records),
            "random_sample": len(random_records),
        },
    }

    for lv, preds in signals.items():
        if not preds:
            continue
        t, c, w, pa, h = calc_hit_rate(preds)
        report["by_signal"][lv] = {
            "count": len(preds),
            "hit_rate": round(h, 3),
            "ratio": round(len(preds) / total_predictions, 3) if total_predictions else 0,
        }

    for dm, preds in domains.items():
        if not preds:
            continue
        t, c, w, pa, h = calc_hit_rate(preds)
        report["by_domain"][dm] = {
            "count": len(preds),
            "hit_rate": round(h, 3),
        }

    for reason, count in error_reasons.most_common(10):
        report["common_errors"].append({
            "pattern": error_labels.get(reason, reason),
            "count": count,
        })

    # 读取上次报告用于对比
    cache_path = os.path.join(FEEDBACK_DIR, "report_cache.json")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                prev = json.load(f)
            report["previous_report"] = {
                "generated_at": prev.get("generated_at", ""),
                "overall_accuracy": prev.get("overall_accuracy", 0),
                "total_samples": prev.get("total_samples", 0),
            }
        except:
            pass

    return report


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='紫微验盘反馈聚合分析')
    parser.add_argument('--verbose', action='store_true', help='显示逐条详情')
    parser.add_argument('--limit', type=int, default=None, help='只分析最近N条')
    parser.add_argument('--output', type=str, default=None, help='输出报告 JSON 到指定路径')
    parser.add_argument('--compare', type=str, default=None, help='与指定的历史报告文件对比')
    args = parser.parse_args()

    records = load_feedbacks(limit=args.limit)
    report = analyze(records, verbose=args.verbose)

    if args.output:
        output_path = args.output
        if not os.path.isabs(output_path):
            output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), output_path)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"报告已保存: {output_path}")
        print(f"  → 在线查看: /api/ziwei/feedback/report?format=html")
