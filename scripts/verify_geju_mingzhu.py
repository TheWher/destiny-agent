# -*- coding: utf-8 -*-
"""
verify_geju_mingzhu.py — 日月系格局口径断言脚本（日月并明 / 明珠出海）

背景（2026-08-04 King 盘审查修正触发）："日月并明"定义存在口径分歧。
2026-08-05 King 拍板：**并存**（各自独立判定、各自带出处，不二选一）。
同日 hanako 翻书校正（《斗数全书》《骨髓赋》王亭之《太微赋》精解）：
日月并明的古籍本义是"庙旺会照"（守不如照），丑未同宫版被王亭之拆台
（丑宫太阴入庙而太阳失地，总有一颗欠缺明朗），故同宫为变体不单列；
明珠出海为古诀专名（《全书》『日卯月亥安命未多折桂』+《骨髓赋》『三合明珠生旺地』）。
巳酉（刘韫龄命丑天梁例）/辰戌（王亭之）变体未单独立格，遇实例再固化。

引擎判定（ziwei_calculator.py 日月系区块）：
- 日月并明 = 太阳太阴各居庙旺 + 均会照命三方（不同宫）
- 明珠出海 = 太阳卯庙 + 太阴亥庙 + 命坐未

本脚本把并存两格写成独立断言，同盘各跑一遍，输出不合并、不选边。
改动格局表/定义后必跑，零差才算过（exit 0）。期望值锚定引擎实测，禁止人脑推导直接写期望。

用法：python scripts/verify_geju_mingzhu.py
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, __file__.rsplit('scripts', 1)[0] or '.')

import ziwei_calculator as z

# ============ 期望值（写死，改动需三思 + 双人复核）============
# King 盘：2005-08-19 01:35 男，命未，太阳卯庙+太阴亥庙。
# 庙旺会照版日月并明=命中（卯亥均在命未三方四正）；明珠出海=命中（古诀专名）。
KING_BIRTH = (2005, 8, 19, 1, 35, '男')
EXPECT_KING = {
    '日月并明': True,   # 庙旺会照版：太阳卯庙+太阴亥庙会照命三方
    '明珠出海': True,    # 古诀：日卯月亥安命未
}
# 拆台样本：2005-01-15 00:30 男，命丑，太阳太阴同守命宫丑。
# 王亭之《太微赋》精解：丑宫太阴入庙而太阳失地，根本谈不上日月并明 → 双判无。
DEMO_BIRTH = (2005, 1, 15, 0, 30, '男')
EXPECT_DEMO = {
    '日月并明': False,   # 同宫丑被拆台（太阳失地）
    '明珠出海': False,   # 命非未
}
# 巳酉变体：2005-01-23 00:30 男，命丑天梁+太阳巳+太阴酉（刘韫龄正例结构）。
# 庙旺会照版命中；明珠出海命非未判无。
SIYOU_BIRTH = (2005, 1, 23, 0, 30, '男')
EXPECT_SIYOU = {
    '日月并明': True,    # 太阳巳庙+太阴酉庙会照命三方
    '明珠出海': False,
}


def _patterns(birth):
    d = z.ziwei_paipan(*birth)
    return {p['name'] for p in z.detect_patterns(d)}


def run():
    failures = []

    def check(name, cond, detail):
        if cond:
            print(f"  [PASS] {name}")
        else:
            print(f"  [FAIL] {name}: {detail}")
            failures.append(name)

    for label, birth, expect in (('King盘(命未,日卯月亥)', KING_BIRTH, EXPECT_KING),
                                 ('拆台样本(命丑,日月同宫)', DEMO_BIRTH, EXPECT_DEMO),
                                 ('巳酉变体(命丑,日巳月酉)', SIYOU_BIRTH, EXPECT_SIYOU)):
        print(f"== {label} 口径并存断言 ==")
        got = _patterns(birth)
        for geju, want in expect.items():
            check(f"{label} {geju} == {'命中' if want else '判无'}",
                  (geju in got) == want,
                  f"got={'命中' if geju in got else '判无'}, want={'命中' if want else '判无'}")

    print()
    if failures:
        print(f"FAIL {len(failures)} 项，exit 1")
        sys.exit(1)
    print("全部通过（3 盘 × 2 格局 = 6 断言），exit 0")


if __name__ == '__main__':
    run()
