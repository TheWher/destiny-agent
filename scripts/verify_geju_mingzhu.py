# -*- coding: utf-8 -*-
"""
verify_geju_mingzhu.py — 日月系格局口径断言脚本（日月并明 / 明珠出海）

背景（2026-08-04 King 盘审查修正触发）："日月并明"定义存在口径分歧——
同宫版（太阳太阴同守命宫，引擎现行定义）vs 取象派明珠出海（太阳卯庙+太阴亥庙+命坐未）。
2026-08-05 King 拍板：**并存**（两格局各自独立判定、各自带出处，不二选一），
引擎格局表已补明珠出海（ziwei_calculator.py 日月系区块）。
修订痕迹样式：King 拍板"不用"，产品层不显示修订痕迹，修正日志仍走 feedback 闭环库。

本脚本把两套定义写成独立断言，同盘各跑一遍，输出不合并、不选边。
改动格局表/定义后必跑，零差才算过（exit 0）。期望值锚定引擎实测，禁止人脑推导直接写期望。

用法：python scripts/verify_geju_mingzhu.py
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, __file__.rsplit('scripts', 1)[0] or '.')

import ziwei_calculator as z

# ============ 期望值（写死，改动需三思 + 双人复核）============
# King 盘：2005-08-19 01:35 男，命未。太阳卯庙+太阴亥庙+命坐未 → 明珠出海命中；同宫版日月并明判无
KING_BIRTH = (2005, 8, 19, 1, 35, '男')
EXPECT_KING = {
    '日月并明': False,   # 同宫版：命宫未无太阳太阴同守
    '明珠出海': True,    # 取象派：太阳卯庙+太阴亥庙+命坐未
}
# 正向样本：2005-01-15 00:30 男，命丑，太阳太阴同守命宫 → 同宫版日月并明命中（明珠出海不命中）
POS_BIRTH = (2005, 1, 15, 0, 30, '男')
EXPECT_POS = {
    '日月并明': True,
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

    for label, birth, expect in (('King盘(命未,太阳卯太阴亥)', KING_BIRTH, EXPECT_KING),
                                 ('正向样本(命丑,日月同守命宫)', POS_BIRTH, EXPECT_POS)):
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
    print("全部通过（2 盘 × 2 格局 = 4 断言），exit 0")


if __name__ == '__main__':
    run()
