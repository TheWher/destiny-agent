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

盘型标签（挂钩 CLAUDE.md 第④条数据来源标签，2026-08-05 定）：
- 真盘 = 本人确认（生辰本人确认过，如 King 盘）
- 待确认盘 = 用户自称（app 用户盘仅到"用户自称"来源级，不得标真盘）
- 古籍例盘 = 二手书证（有权威出处但无活人确认，如刘韫龄巳酉正例；King 翻书真翻到例盘时当实例，先记备注不立格）
- 构造盘 = 推导/合成（无现实锚，验规则自洽）
统计分开算：构造盘全过验的是规则自洽，规则跟现实对不对得上锚点是真盘；真盘攒够再谈强度（与"字段长在实例里"同构）。

用法：python scripts/verify_geju_mingzhu.py
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, __file__.rsplit('scripts', 1)[0] or '.')

import ziwei_calculator as z

# ============ 期望值（写死，改动需三思 + 双人复核）============
# 2026-08-05 教训：判"某年生"必须跑引擎/check_ganzhi，不许按公历口头定年（立春界）。
# 原巳酉变体 2005-01-23 在立春(2/4)前 = 甲申年，"辛乙生人合格"不满足，已换真乙酉年盘。
# 每盘年干写死为引擎 year_gz 期望值，造盘强制干支校验（源头拦，比事后核便宜）。

# King 盘：2005-08-19 01:35 男，命未，太阳卯庙+太阴亥庙。
# 庙旺会照版日月并明=命中（卯亥均在命未三方四正）；明珠出海=命中（古诀专名）。
KING_BIRTH = (2005, 8, 19, 1, 35, '男')
EXPECT_KING = {
    'year_gz': '乙酉',  # 来源=本人确认（King 生辰基线）
    '日月并明': True,   # 庙旺会照版：太阳卯庙+太阴亥庙会照命三方
    '明珠出海': True,    # 古诀：日卯月亥安命未
}
# 拆台样本：2005-01-15 00:30 男，命丑，太阳太阴同守命宫丑。
# 王亭之《太微赋》精解：丑宫太阴入庙而太阳失地，根本谈不上日月并明 → 双判无。
DEMO_BIRTH = (2005, 1, 15, 0, 30, '男')
EXPECT_DEMO = {
    'year_gz': '甲申',  # 来源=引擎口径（构造盘，2026-08-05 引擎实测）
    '日月并明': False,   # 同宫丑被拆台（太阳失地）
    '明珠出海': False,   # 命非未
}
# 巳酉变体：2005-02-06 00:30 男（立春后，真乙酉年），命丑天梁+太阳巳+太阴酉。
# 《骨髓赋》注文『安命丑宫，日在巳、月在酉来朝照，为并明，辛乙生人合格』——
# 真乙酉年生满足"乙"合格条件，古籍标准例与断言盘逐字对应。
# 旧盘 2005-01-23 是甲申年（立春前），不满足，2026-08-05 换盘。
SIYOU_BIRTH = (2005, 2, 6, 0, 30, '男')
EXPECT_SIYOU = {
    'year_gz': '乙酉',  # 来源=引擎口径（构造盘，2026-08-05 引擎实测，立春后）
    '日月并明': True,    # 太阳巳庙+太阴酉庙会照命三方
    '明珠出海': False,
}
# 对宫分支（王亭之辰戌）：2005-01-19 18:30 男，命辰，太阳辰（命宫自身）+太阴戌（对宫）。
# 四方四正分支矩阵第 4 支：对宫（idx+6）。手工实测命中，补进断言防回归漏判。
DUIGONG_BIRTH = (2005, 1, 19, 18, 30, '男')
EXPECT_DUIGONG = {
    'year_gz': '甲申',  # 来源=引擎口径（构造盘，2026-08-05 引擎实测）
    '日月并明': True,    # 太阳辰庙+太阴戌庙，命辰自身+对宫
    '明珠出海': False,
}
# 自身分支（刘韫龄正例一）：2005-01-01 14:30 男，命巳，太阳巳（命宫自身）+太阴酉（三合）。
# 四方四正分支矩阵第 1 支：命宫自身（idx+0）。手工实测命中，补进断言防回归漏判。
ZISHEN_BIRTH = (2005, 1, 1, 14, 30, '男')
EXPECT_ZISHEN = {
    'year_gz': '甲申',  # 来源=引擎口径（构造盘，2026-08-05 引擎实测）
    '日月并明': True,    # 太阳巳庙坐命+太阴酉庙会照
    '明珠出海': False,
}
# 古籍例盘（《星源集庆》道光帝）：乾隆四十七年壬寅八月初十甲戌日丙寅时，明珠出海格。
# 公历 1782-09-16 寅时，引擎实测：命未+日卯月亥+壬寅年干，日月并明+明珠出海双命中。
# 出处：白洋工作室引《星源集庆》（道光帝命例）+《全书》『日卯月亥安命未宫多折桂』+《骨髓赋》『三合明珠生旺地稳步蟾宫』。
# 盘型=古籍例盘（有权威出处但无活人确认，2026-08-05 网络查证补入）。
DAOGUANG_BIRTH = (1782, 9, 16, 4, 30, '男')
EXPECT_DAOGUANG = {
    'year_gz': '壬寅',  # 来源=古籍（《星源集庆》乾隆四十七年壬寅，引擎实测一致）
    '日月并明': True,
    '明珠出海': True,
}


def _patterns(birth):
    d = z.ziwei_paipan(*birth)
    return {p['name'] for p in z.detect_patterns(d)}, d.get('year_gz', '')


def run():
    failures = []

    def check(name, cond, detail):
        if cond:
            print(f"  [PASS] {name}")
        else:
            print(f"  [FAIL] {name}: {detail}")
            failures.append(name)

    for label, birth, expect, kind in (
            ('King盘(命未,日卯月亥)', KING_BIRTH, EXPECT_KING, '真盘'),
            ('拆台样本(命丑,日月同宫)', DEMO_BIRTH, EXPECT_DEMO, '构造盘'),
            ('巳酉变体(命丑,日巳月酉)', SIYOU_BIRTH, EXPECT_SIYOU, '构造盘'),
            ('对宫分支(命辰,日辰月戌)', DUIGONG_BIRTH, EXPECT_DUIGONG, '构造盘'),
            ('自身分支(命巳,日坐命月酉)', ZISHEN_BIRTH, EXPECT_ZISHEN, '构造盘'),
            ('古籍例盘(道光帝,命未日卯月亥)', DAOGUANG_BIRTH, EXPECT_DAOGUANG, '古籍例盘')):
        print(f"== [{kind}] {label} 口径并存断言 ==")
        got, got_gz = _patterns(birth)
        want_gz = expect.pop('year_gz')
        check(f"[{kind}] {label} 年干 == {want_gz}",
              got_gz == want_gz,
              f"got={got_gz}, want={want_gz}（引擎 year_gz，立春界，禁公历口头定年）")
        for geju, want in expect.items():
            check(f"[{kind}] {label} {geju} == {'命中' if want else '判无'}",
                  (geju in got) == want,
                  f"got={'命中' if geju in got else '判无'}, want={'命中' if want else '判无'}")
        expect['year_gz'] = want_gz

    print()
    real = [f for f in failures if '真盘' in f]
    if failures:
        print(f"FAIL {len(failures)} 项（真盘 {len(real)} / 构造盘 {len(failures)-len(real)}），exit 1")
        sys.exit(1)
    print("全部通过（6 盘 × 3 断言 = 18 条：年干 6 + 双格局 12；真盘 3 / 构造盘 12 / 古籍例盘 3，四方四正四分支+古籍例盘+年干校验全钉），exit 0")


if __name__ == '__main__':
    run()
