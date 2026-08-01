#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""评测集 dry-run 校验：对每个 pair 跑真实 retrieve_kb，验证答案在 top-k 返回内。

口径：exact_contain（归一化后标准答案为返回段落子串即算中），k=5。
不通过列表用于排查，不修改数据。
"""
import json
import pathlib
import re
import sys

PROJ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ))
from services.kb_loader import retrieve_kb, retrieve_hits  # noqa: E402

DS = pathlib.Path(__file__).resolve().parent / "seed_pairs.json"
K = 5


def norm(s: str) -> str:
    """归一化：去空白/全半角/标点/json 转义符（表示层污染剥离）"""
    s = re.sub(r"[\s\u3000]+", "", s)
    # 全角 → 半角（0xFF01-0xFF5E → 0x21-0x7E）
    s = s.translate(str.maketrans({chr(c): chr(c - 0xFEE0) for c in range(0xFF01, 0xFF5F)}))
    s = s.replace("\\", "")  # json.dumps 的转义反斜杠（\" 等）是表示层污染
    s = re.sub(r"[，。、；：？！「」『』（）《》\"'.,;:!?()\[\]{}]", "", s)
    return s


def answer_text(pair: dict) -> str:
    t = pair["target"]
    fn = t["file"]
    kb_path = PROJ / "knowledge_base" / fn
    kb = json.load(open(kb_path, encoding="utf-8"))
    if fn == "ziwei_classics_full.json":
        return kb["paragraphs"][t["key"]["index"]]["text"]
    if fn == "ziwei_classics.json":
        return kb["patterns"][t["key"]]
    if fn == "tiaohou.json":
        k = t["key"]
        return json.dumps(kb["table"][k["gan"]][k["zhi"]], ensure_ascii=False)
    if fn == "ziwei_hua.json":
        return kb["interpretation"][t["key"]["hua"]]["in_palace_guide"][t["key"]["palace"]]
    if fn == "ziwei_star_palace.json":
        pal = kb["stars"][t["key"]["star"]]["palaces"][t["key"]["palace"]]
        return json.dumps(pal, ensure_ascii=False)
    if fn == "ziwei_fuzuo.json":
        return kb[t["key"]["star"]]["分宫"][t["key"]["palace"]]
    return ""


def consistency_check(kws: list, fn: str) -> bool:
    """第三道校验：同一 keywords 下 hits 名单与 str 文本互相对应。

    两个出口（retrieve_kb str / retrieve_hits 名单）必须共享同一匹配引擎；
    若实现漂移（hits 返回了 str 里没有的条目），一致性断言在此抓出。
    匹配口径：hit id 文本须出现在 str 中。lexical 阶段 str 是块级 dump（hits 的超集，
    条目内容以子串形式存在）；embedding 条目级后两者条目头同构，同一断言收敛为强一致。
    """
    try:
        hits = retrieve_hits(kws, fn, top_k=K)
        if not hits:
            return True
        s = retrieve_kb(kws, fn, top_k=K)
        return all(h in s for h in hits)
    except Exception:
        return False


def main():
    ds = json.load(open(DS, encoding="utf-8"))
    pairs = ds["pairs"]
    passed, failed, skipped = [], [], []
    consistency_ok, consistency_bad = 0, 0
    # 粒度统计：按文件聚合返回长度（命中率之外的第二指标，粒度差会稀释命中率含金量）
    from collections import defaultdict
    len_by_file = defaultdict(list)
    for p in pairs:
        t = p["target"]
        fn = t["file"]
        # 已毕业留档（classics_full 登记化后不参与评测）：跳过不跑，报告单列
        if p.get("status") == "graduated":
            skipped.append(p["id"])
            continue
        kws = p.get("keywords", [])
        # 空关键词跳过（理论上不该发生）
        if not kws:
            failed.append((p["id"], "empty keywords"))
            continue
        try:
            res = retrieve_kb(kws, fn, top_k=K)
        except Exception as e:
            failed.append((p["id"], f"retrieve exception: {e}"))
            continue
        len_by_file[fn].append(len(res))
        ans = norm(answer_text(p))
        if not ans:
            failed.append((p["id"], "empty answer"))
            continue
        if ans in norm(res):
            passed.append(p["id"])
        else:
            failed.append((p["id"], f"answer not in top-{K}"))
        # 第三道校验：hits↔str 一致性（不阻塞命中判定，单独统计）
        if consistency_check(kws, fn):
            consistency_ok += 1
        else:
            consistency_bad += 1

    total_run = len(pairs) - len(skipped)
    print(f"total={len(pairs)} run={total_run} passed={len(passed)} failed={len(failed)} skipped={len(skipped)}")
    if skipped:
        print(f"已毕业留档（跳过不跑）: {len(skipped)} 对 (cff_*)")
    if total_run:
        print(f"pass rate: {len(passed)/total_run*100:.1f}%")
    print(f"hits↔str 一致性: {consistency_ok}/{consistency_ok+consistency_bad}")

    # 粒度页：按文件返回长度分布（min/avg/max），粒度本身是评测维度
    # 文件级判定（动态，不依赖后端）：返回长度接近文件整体 → 整文件 dump（粒度注水特征）
    # lexical 基线：classics_full 7934B≈文件大小、tiaohou 6.4KB≈表大小、classics 1707B 均判文件级
    # embedding：返回 109~703B，远小于文件大小，全部条目级（对应验收线"文件级对→0"）
    KB_DIR = PROJ / "knowledge_base"

    def _is_file_level(fn: str, res_len: int) -> bool:
        try:
            size = (KB_DIR / fn).stat().st_size
        except OSError:
            size = 0
        return res_len >= max(1600, size * 0.5)

    file_cnt, non_file_cnt = 0, 0
    print("\n返回长度分布（字节，按文件）:")
    print(f"  {'file':<30} {'n':>3} {'min':>7} {'avg':>8} {'max':>7} {'file-level':>10}")
    all_lens = []
    for fn in sorted(len_by_file):
        lens = len_by_file[fn]
        all_lens.extend(lens)
        fl = sum(1 for L in lens if _is_file_level(fn, L))
        file_cnt += fl
        non_file_cnt += len(lens) - fl
        print(f"  {fn:<30} {len(lens):>3} {min(lens):>7} {sum(lens)//len(lens):>8} {max(lens):>7} {fl:>7}/{len(lens):<3}")
    if all_lens:
        print(f"  {'ALL':<30} {len(all_lens):>3} {min(all_lens):>7} {sum(all_lens)//len(all_lens):>8} {max(all_lens):>7} {file_cnt:>7}/{len(all_lens):<3}")
        coarse = sum(1 for L in all_lens if L >= 1600)
        print(f"\n粒度注水比（返回>=1.6KB 的 pair 占比）: {coarse}/{len(all_lens)} = {coarse/len(all_lens)*100:.0f}%")
        print(f"返回单位构成（动态判定）: 文件级 {file_cnt} / 条目级及以下 {non_file_cnt}")
        # 验收线基准（lexical 基线：文件级 27、平均 2423B；embedding 上线后对比）
        avg_len = sum(all_lens) // len(all_lens)
        print(f"\n[验收线基准] 文件级对={file_cnt}（目标 0） 平均返回长度={avg_len}（目标 <= 减半）")
        # 三态判定（韩湘生定案验收标准）
        print("\n[验收判定]")
        print(f"  文件级对: {file_cnt} -> {'PASS' if file_cnt == 0 else '未达标（目标 0）'}")
        if avg_len <= 1100:
            verdict = "优良（~1KB，接近条目级）"
        elif avg_len <= 1640:
            verdict = "及格（减半达标）"
        else:
            verdict = "未达标（需 <=1640 减半）"
        print(f"  平均返回长度: {avg_len}B -> {verdict}")

    if failed:
        print("\nFAILED:")
        for pid, reason in failed:
            print(f"  {pid}: {reason}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
