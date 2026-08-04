# -*- coding: utf-8 -*-
"""
verify_laiyin_anchors.py — 来因宫判别式双锚校验尺断言脚本

背景（2026-08-04 教训）：旧判别式"甲己恒在戌"把"甲己同遁"偷换成"甲己同位"，
仅甲-戊成立。验证要对断言本身负责，不能只对底层算术负责（同"探针自洽≠现状正确"）。
本脚本把十干落位表写死为期望值，改动校验尺/清单条目后必跑，零差才算过（exit 0）。断言分两层：数学层（五虎遁/同阴阳，纯数学自洽，不依赖引擎）+ 宫位/口径层（期望值必须锚定引擎实测，禁止人脑推导直接写期望，推导只当假设）。引擎实测是仲裁（当日两次救命：干支口径、布宫方向）。

用法：python scripts/verify_laiyin_anchors.py
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

GANS = "甲乙丙丁戊己庚辛壬癸"
ZHIS = "子丑寅卯辰巳午未申酉戌亥"
# 五虎遁起月天干索引：甲己→丙(2)，乙庚→戊(4)，丙辛→庚(6)，丁壬→壬(8)，戊癸→甲(0)；起月地支恒为寅(2)
START_STEM = {"甲": 2, "己": 2, "乙": 4, "庚": 4, "丙": 6, "辛": 6, "丁": 8, "壬": 8, "戊": 0, "癸": 0}
PAIR_FIRST = {"甲": "甲", "己": "甲", "乙": "乙", "庚": "乙", "丙": "丙", "辛": "丙",
              "丁": "丁", "壬": "丁", "戊": "戊", "癸": "戊"}

# ============ 期望值（写死，改动需三思 + 全组复核）============
EXPECT_INDIVIDUAL = {  # 个体制（宫干=生年干），候选位列表
    "甲": ["戌"], "乙": ["酉"], "丙": ["申"], "丁": ["未"], "戊": ["午"],
    "己": ["巳"], "庚": ["辰"], "辛": ["卯", "丑"], "壬": ["寅", "子"], "癸": ["亥"],
}
EXPECT_PAIR = {  # 对首制（五组对锚），恒唯一
    "甲": "戌", "己": "戌", "乙": "酉", "庚": "酉", "丙": "申",
    "辛": "申", "丁": "未", "壬": "未", "戊": "午", "癸": "午",
}
EXPECT_SAME = "甲乙丙丁戊"          # 两制重合干（例盘对这两制无效）
EXPECT_DIFF = "己庚辛壬癸"          # 两制岔开干（判别样本）
EXPECT_PARENT_WITH_MING_HAI = "子"  # 命宫落亥 → 子位 = 父母宫（引擎逆布口径：父母=命+1）
# 2026-08-04 修正：旧版用顺布公式（父母=命+11）得戌，引擎实测 iztro 为逆布（父母=命+1），命亥父母实为子。
# 错误史：此断言 18:44 过目与首轮复核共享同一顺布方向假设，两层全绿仍错，直到 King 真盘数据照出。验证链各层须独立检查基础假设。


def months(y):
    si = START_STEM[y]
    return [GANS[(si + k) % 10] + ZHIS[(2 + k) % 12] for k in range(12)]


def individual(y):
    return [m[1] for m in months(y) if m[0] == y]


def pair_anchor(y):
    return individual(PAIR_FIRST[y])[0]


def run():
    failures = []

    def check(name, cond, detail):
        if cond:
            print(f"  [PASS] {name}")
        else:
            print(f"  [FAIL] {name}: {detail}")
            failures.append(name)

    print("== 个体制（宫干=生年干）逐干断言 ==")
    for y in GANS:
        got = individual(y)
        check(f"{y}年 个体制 {got} == {EXPECT_INDIVIDUAL[y]}",
              got == EXPECT_INDIVIDUAL[y], f"got={got}")

    print("== 对首制（五组对锚）逐干断言 ==")
    for y in GANS:
        got = pair_anchor(y)
        check(f"{y}年 对首制 {got} == {EXPECT_PAIR[y]}",
              got == EXPECT_PAIR[y], f"got={got}")

    print("== 两制重合/岔开集合断言 ==")
    same = "".join(y for y in GANS if set(individual(y)) == {pair_anchor(y)})
    diff = "".join(y for y in GANS if set(individual(y)) != {pair_anchor(y)})
    check(f"重合干 == {EXPECT_SAME}", same == EXPECT_SAME, f"got={same}")
    check(f"岔开干 == {EXPECT_DIFF}", diff == EXPECT_DIFF, f"got={diff}")

    print("== 数学层断言：子丑恒重复寅卯（五虎遁 12 位 10 干必两重复，纯数学必然）==")
    for y in GANS:
        ms = months(y)
        check(f"{y}年 子位干==寅位干（{ms[10][0]}=={ms[0][0]}）",
              ms[10][0] == ms[0][0], f"got {ms[10][0]} vs {ms[0][0]}")
        check(f"{y}年 丑位干==卯位干（{ms[11][0]}=={ms[1][0]}）",
              ms[11][0] == ms[1][0], f"got {ms[11][0]} vs {ms[1][0]}")

    print("== 双候选位仅辛壬断言 ==")
    doubles = "".join(y for y in GANS if len(individual(y)) > 1)
    check("双候选干 == 辛壬", doubles == "辛壬", f"got={doubles}")

    print("== 60甲子性质断言：任何盘任何宫干位必然干支同阴阳（翻面论证）==")
    for y in GANS:
        bad = [m for m in months(y) if (GANS.index(m[0]) % 2) != (ZHIS.index(m[1]) % 2)]
        check(f"{y}年 12 宫干位全部同阴阳", not bad, f"异阴阳位: {bad}")

    print("== 个体制锚全同阴阳 / 对首制己-癸锚全异阴阳断言 ==")
    for y, pos in EXPECT_INDIVIDUAL.items():
        bad = [z for z in pos if (GANS.index(y) % 2) != (ZHIS.index(z) % 2)]
        check(f"{y}年个体制锚 {pos} 全同阴阳", not bad, f"异阴阳: {bad}")
    for y, z in [("己", "戌"), ("庚", "酉"), ("辛", "申"), ("壬", "未"), ("癸", "午")]:
        same = (GANS.index(y) % 2) == (ZHIS.index(z) % 2)
        check(f"{y}年对首制锚 {z} 为异阴阳（排除出局）", not same, f"{y}{z} 竟然同阴阳")

    print("== 命宫落亥 → 父母宫地支位断言（逆布，引擎口径）==")
    parent = ZHIS[(ZHIS.index("亥") + 1) % 12]
    check(f"命宫落亥父母宫位 == {EXPECT_PARENT_WITH_MING_HAI}",
          parent == EXPECT_PARENT_WITH_MING_HAI, f"got={parent}")

    print("== King 真盘回归断言（引擎实测 2005-08-19 01:35 男 东莞 113.75）==")
    ming = ZHIS.index("未")
    check("命未 → 福德酉（命+2，逆布）", ZHIS[(ming + 2) % 12] == "酉",
          f"got={ZHIS[(ming + 2) % 12]}")
    check("命未 → 父母申（命+1，逆布）", ZHIS[(ming + 1) % 12] == "申",
          f"got={ZHIS[(ming + 1) % 12]}")

    print()
    if failures:
        print(f"FAILED: {len(failures)} 项断言未过 -> {failures}")
        sys.exit(1)
    print("ALL PASS：十干落位 + 双锚集合 + 两维重合条件全部与写死期望一致")


if __name__ == "__main__":
    run()
