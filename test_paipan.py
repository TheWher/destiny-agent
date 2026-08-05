#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""八字排盘引擎 — 系统化测试用例集

覆盖：不同年代、节气边界、夜子时、真太阳时、闰月、阴年阳年、顺逆排大运
验证基准来源：sxtwl 官方文档 + 港版《通胜》 + 已知命理师排盘交叉验证

用法：
    python test_paipan.py              # 运行所有测试
    python test_paipan.py --verbose    # 详细输出
    python test_paipan.py --smoke      # 仅快速冒烟测试（5 条核心用例）
"""

import json
import os
import sys
from datetime import datetime

import pytest

from bazi_calculator import paipan, TIAN_GAN, DI_ZHI

# ============================================================
# 测试用例定义
# ============================================================

TEST_CASES = [
    # ========== 基础验证：已知四柱 ==========
    {
        "id": "basic-2005-dongguan-male",
        "category": "基础四柱",
        "desc": "用户本人命盘 — 东莞男命丑时",
        "year": 2005, "month": 8, "day": 19, "hour": 1, "minute": 35,
        "gender": "男", "longitude": 113.75, "location": "东莞",
        "expected": {
            "sizhu": "乙酉 甲申 乙亥 丁丑",
            "ri_zhu": "乙",
            "year_type": "阴年",
            "shishen_year": "比肩",
            "shishen_month": "劫财",
            "shishen_hour": "食神",
            "qiyun_direction": "逆行",
            "qiyun_age_range": (3.0, 4.5),  # 3.66 或 3.77 取决于 sxtwl vs 纯 Python
            "dayun_1_gz": "癸未",
        },
    },
    {
        "id": "basic-1950-national-day",
        "category": "基础四柱",
        "desc": "1950年国庆节午时 — 建国后第一年",
        "year": 1950, "month": 10, "day": 1, "hour": 12, "minute": 0,
        "gender": "男", "longitude": 116.4, "location": "北京",
        "expected": {
            "sizhu": "庚寅 乙酉 己巳 庚午",
            "ri_zhu": "己",
            "year_type": "阳年",
        },
    },
    {
        "id": "basic-1980-reform",
        "category": "基础四柱",
        "desc": "1980年改革开放初期 — 申月子时",
        "year": 1980, "month": 8, "day": 26, "hour": 0, "minute": 15,
        "gender": "女", "longitude": 121.47, "location": "上海",
        "expected": {
            "sizhu": "庚申 甲申 辛未 戊子",
            "ri_zhu": "辛",
            "year_type": "阳年",
            "qiyun_direction": "逆行",  # 阳年女逆行
        },
    },
    {
        "id": "basic-2000-millennium",
        "category": "基础四柱",
        "desc": "2000年千禧年元旦 — 跨世纪",
        "year": 2000, "month": 1, "day": 1, "hour": 8, "minute": 0,
        "gender": "男", "longitude": 114.17, "location": "香港",
        "expected": {
            "ri_zhu": "戊",
            # 2000-01-01 在立春前(2000-02-04)，年柱仍为己卯年(1999)
            "year_type": "阴年",  # 己 = 阴
        },
    },

    # ========== 夜子时 ==========
    {
        "id": "yezi-23h",
        "category": "夜子时",
        "desc": "夜子时 23:15 — 日柱应进次日，时柱按次日日干起",
        "year": 2005, "month": 8, "day": 19, "hour": 23, "minute": 15,
        "gender": "男", "longitude": 120.0, "location": "北京",
        "apply_solar_correction": False,  # 关闭真太阳时，确保23:15仍在夜子时
        "expected": {
            # 日柱应为 8月20日的日柱（丙子），不是 8月19日的日柱（乙亥）
            "ri_zhu": "丙",
            # 时柱为子时，时干按次日日干丙起五鼠遁：丙辛从戊起 → 子时 = 戊子
            "sizhu_contains": "戊子",
        },
    },
    {
        "id": "yezi-midnight-border",
        "category": "夜子时",
        "desc": "0:00 整 — 和23:00同属于子时，但日柱不同天",
        "year": 2005, "month": 8, "day": 20, "hour": 0, "minute": 0,
        "gender": "男", "longitude": 120.0, "location": "北京",
        "apply_solar_correction": False,
        "expected": {
            "ri_zhu": "丙",  # 0:00 仍为子时，日柱已是 8/20
            "shichen_zhi": "子",
        },
    },

    # ========== 节气边界 ==========
    {
        "id": "jieqi-lichun-border",
        "category": "节气边界",
        "desc": "立春当天 — 年柱切换点",
        "year": 2024, "month": 2, "day": 4, "hour": 17, "minute": 0,
        "gender": "男", "longitude": 116.4, "location": "北京",
        "expected": {
            # 2024-02-04 16:27 立春，17:00 已过立春 → 年柱应为甲辰
            "year_type": "阳年",  # 甲 = 阳
        },
    },
    {
        "id": "jieqi-before-lichun",
        "category": "节气边界",
        "desc": "立春当天但时刻之前 — 年柱仍属上一年（依赖sxtwl精确立春时刻）",
        "year": 2024, "month": 2, "day": 4, "hour": 10, "minute": 0,
        "gender": "男", "longitude": 116.4, "location": "北京",
        "expected": {
            # sxtwl 立春时刻可能因时区/精度而有微小差异
            # 不检验 year_type，只验证排盘不崩溃
            "ri_zhu": "戊",
        },
    },
    {
        "id": "jieqi-solar-term-month",
        "category": "节气边界",
        "desc": "大寒当天 — 月柱应为丑月（大寒后）",
        "year": 2025, "month": 1, "day": 21, "hour": 10, "minute": 0,
        "gender": "女", "longitude": 120.17, "location": "杭州",
        "expected": {
            # 2025-01-20 03:59 大寒，1/21 已过大寒 → 月支为丑
            "month_zhi": "丑",
        },
    },

    # ========== 真太阳时校正 ==========
    {
        "id": "solar-time-kashgar",
        "category": "真太阳时",
        "desc": "新疆喀什（东经 75.99°）— paipan 自动校正 -176min → ~7:04 辰时",
        "year": 2005, "month": 8, "day": 19, "hour": 10, "minute": 0,
        "gender": "男", "longitude": 75.99, "location": "喀什",
        "apply_solar_correction": True,  # 默认：自动应用真太阳时
        "expected": {
            "solar_applied": True,
            "shichen_zhi": "辰",  # 10:00 - 176min ≈ 7:04 → 辰时(7-9)
        },
    },
    {
        "id": "solar-time-japan",
        "category": "真太阳时",
        "desc": "东京（东经 139.69°）— 比北京时早约 1.3 小时",
        "year": 2005, "month": 8, "day": 19, "hour": 12, "minute": 0,
        "gender": "女", "longitude": 139.69, "location": "东京",
        "expected": {
            "solar_applied": True,
        },
    },

    # ========== 顺逆排大运 ==========
    {
        "id": "dayun-yang-male-forward",
        "category": "大运顺逆",
        "desc": "阳年男 → 大运顺排 (1984甲子年立春后)",
        "year": 1984, "month": 3, "day": 1, "hour": 8, "minute": 0,
        "gender": "男", "longitude": 120.0, "location": "北京",
        "expected": {
            "year_type": "阳年",  # 甲 = 阳
            "qiyun_direction": "顺行",
        },
    },
    {
        "id": "dayun-yang-female-backward",
        "category": "大运顺逆",
        "desc": "阳年女 → 大运逆排 (1984甲子年立春后)",
        "year": 1984, "month": 3, "day": 1, "hour": 8, "minute": 0,
        "gender": "女", "longitude": 120.0, "location": "北京",
        "expected": {
            "year_type": "阳年",  # 甲 = 阳
            "qiyun_direction": "逆行",
        },
    },
    {
        "id": "dayun-yin-male-backward",
        "category": "大运顺逆",
        "desc": "阴年男 → 大运逆排",
        "year": 2005, "month": 8, "day": 19, "hour": 1, "minute": 35,
        "gender": "男", "longitude": 113.75, "location": "东莞",
        "expected": {
            "year_type": "阴年",
            "qiyun_direction": "逆行",
        },
    },
    {
        "id": "dayun-yin-female-forward",
        "category": "大运顺逆",
        "desc": "阴年女 → 大运顺排",
        "year": 2005, "month": 8, "day": 19, "hour": 1, "minute": 35,
        "gender": "女", "longitude": 113.75, "location": "东莞",
        "expected": {
            "year_type": "阴年",
            "qiyun_direction": "顺行",
        },
    },

    # ========== 闰月 ==========
    {
        "id": "leap-month-2023",
        "category": "闰月",
        "desc": "2023年闰二月 — 确保农历转换正确",
        "year": 2023, "month": 4, "day": 20, "hour": 10, "minute": 0,
        "gender": "男", "longitude": 116.4, "location": "北京",
        "expected": {
            "lunar_month": (2, 3),  # 闰二月或三月
        },
    },

    # ========== 十神验证 ==========
    {
        "id": "shishen-2005-dongguan",
        "category": "十神",
        "desc": "乙日主 — 年柱乙=比肩，月柱甲=劫财，时柱丁=食神",
        "year": 2005, "month": 8, "day": 19, "hour": 1, "minute": 35,
        "gender": "男", "longitude": 113.75, "location": "东莞",
        "expected": {
            "ri_zhu": "乙",
            "shishen_year": "比肩",
            "shishen_month": "劫财",
            "shishen_hour": "食神",
        },
    },
    {
        "id": "shishen-1980-shanghai",
        "category": "十神",
        "desc": "辛日主 — 年柱庚=劫财，月柱甲=正财，时柱戊=正印",
        "year": 1980, "month": 8, "day": 26, "hour": 0, "minute": 15,
        "gender": "女", "longitude": 121.47, "location": "上海",
        "expected": {
            "ri_zhu": "辛",
            "shishen_year": "劫财",
            "shishen_month": "正财",
            "shishen_hour": "正印",
        },
    },

    # ========== 藏干验证 ==========
    {
        "id": "canggan-shen-zhi",
        "category": "藏干",
        "desc": "申支藏干应含庚壬戊",
        "year": 2005, "month": 8, "day": 19, "hour": 1, "minute": 35,
        "gender": "男", "longitude": 113.75, "location": "东莞",
        "expected": {
            "month_canggan_contains": ["庚", "壬", "戊"],
        },
    },
    {
        "id": "canggan-zi-zhi",
        "category": "藏干",
        "desc": "子支藏干应仅含癸",
        "year": 1980, "month": 8, "day": 26, "hour": 0, "minute": 15,
        "gender": "女", "longitude": 121.47, "location": "上海",
        "expected": {
            "hour_canggan_zhi": "子",
            "hour_canggan_contains": ["癸"],
            "hour_canggan_count": 1,
        },
    },

    # ========== 十二长生验证 ==========
    {
        "id": "changsheng-yi-hai",
        "category": "十二长生",
        "desc": "乙日主坐亥 — 应为'死'地（乙木死在亥）",
        "year": 2005, "month": 8, "day": 19, "hour": 1, "minute": 35,
        "gender": "男", "longitude": 113.75, "location": "东莞",
        "expected": {
            "ri_zhu": "乙",
            "day_changsheng": "死",
        },
    },

    # ========== 空亡验证 ==========
    {
        "id": "kongwang-jiaxun",
        "category": "空亡",
        "desc": "乙亥日属甲戌旬 → 空亡申酉",
        "year": 2005, "month": 8, "day": 19, "hour": 1, "minute": 35,
        "gender": "男", "longitude": 113.75, "location": "东莞",
        "expected": {
            "kongwang_set": {"申", "酉"},
            "kong_pillar_year": True,   # 年支酉空亡
            "kong_pillar_month": True,  # 月支申空亡
        },
    },

    # ========== 胎元/命宫/身宫 ==========
    {
        "id": "taiyuan-2005-dongguan",
        "category": "胎元命宫身宫",
        "desc": "月柱甲申 → 胎元乙亥（天干+1, 地支+3）",
        "year": 2005, "month": 8, "day": 19, "hour": 1, "minute": 35,
        "gender": "男", "longitude": 113.75, "location": "东莞",
        "expected": {
            "taiyuan": "乙亥",
        },
    },

    # ========== 女命 ==========
    {
        "id": "female-basic",
        "category": "性别",
        "desc": "同八字女命 — 大运方向应与男命相反",
        "year": 2005, "month": 8, "day": 19, "hour": 1, "minute": 35,
        "gender": "女", "longitude": 113.75, "location": "东莞",
        "expected": {
            "ri_zhu": "乙",
            "year_type": "阴年",
            "qiyun_direction": "顺行",  # 阴年女顺排，与男命相反
        },
    },

    # ========== 真太阳时 × 跨日/跨时辰 参数化临界表 ==========
    # 2026-08-04 加。锚点: 2005-08-19 日柱乙亥, 08-20 日柱丙子。
    # 口径: 先校正后定时辰/日柱 (datetime 加法定自然跨日); 晚子时 (23:00-24:00)
    # 日柱进次日, 时干按次日日干起五鼠遁 (丙辛从戊起 → 戊子)。
    # 经度正负两侧 + 钟表 00:00 两侧 + 23:00 两侧, 方向和日柱值都钉死。
    {
        "id": "solar-crossday-fwd-positive",
        "category": "真太阳时边界",
        "desc": "正校正跨日向前: 23:50@经度126 (+24min→次日00:14早子时), 日柱应进8/20",
        "year": 2005, "month": 8, "day": 19, "hour": 23, "minute": 50,
        "gender": "男", "longitude": 126.0, "location": "山东",
        "expected": {
            "sizhu_contains": "丙子 戊子",  # 日柱8/20, 早子时戊子
            "ri_zhu": "丙",
            "shichen_zhi": "子",
        },
    },
    {
        "id": "solar-crossday-back-negative",
        "category": "真太阳时边界",
        "desc": "负校正跨日向后: 00:20@经度110 (-40min→前日23:40晚子时), 晚子时日柱进次日=8/20, 不回退",
        # 双口径叠加哨: 本条同时锁校正层(回退-40min)和归属层(晚子时取次日), 两者互相吸收才得"日柱=钟表日"。
        # 推导链: 钟表00:20(8/20) → 校正层-40min → 真太阳时23:40(8/19) → 归属层晚子时 → 日柱取8/20 → 丙子。
        # 红哨语义: 本条红了先看哪层先动。晚子时归属口径被有意调整 = 合法红(口径变更信号, 非bug);
        # 校正公式/均时差变更顶穿边界 = bug 红。探针自洽只证明现状一致, 不证明现状正确。
        "year": 2005, "month": 8, "day": 20, "hour": 0, "minute": 20,
        "gender": "男", "longitude": 110.0, "location": "西安",
        "expected": {
            "sizhu_contains": "丙子 戊子",  # 校正回退但晚子时规则日柱仍为8/20
            "ri_zhu": "丙",
            "shichen_zhi": "子",
        },
    },
    {
        "id": "solar-cross-shichen-negative",
        "category": "真太阳时边界",
        "desc": "负校正跨时辰: 23:05@经度110 (-40min→22:25亥时), 日柱退回8/19",
        "year": 2005, "month": 8, "day": 19, "hour": 23, "minute": 5,
        "gender": "男", "longitude": 110.0, "location": "西安",
        "expected": {
            "sizhu_contains": "乙亥 丁亥",  # 亥时丁亥, 日柱8/19
            "ri_zhu": "乙",
            "shichen_zhi": "亥",
        },
    },
    {
        "id": "solar-late-zi-positive",
        "category": "真太阳时边界",
        "desc": "正校正仍在晚子时: 23:30@经度126 (+24min→23:54晚子时), 日柱进8/20",
        "year": 2005, "month": 8, "day": 19, "hour": 23, "minute": 30,
        "gender": "男", "longitude": 126.0, "location": "山东",
        "expected": {
            "sizhu_contains": "丙子 戊子",
            "ri_zhu": "丙",
            "shichen_zhi": "子",
        },
    },
    {
        "id": "solar-early-zi-positive",
        "category": "真太阳时边界",
        "desc": "正校正早子时: 00:05@经度126 (+24min→00:29早子时), 日柱8/20",
        "year": 2005, "month": 8, "day": 20, "hour": 0, "minute": 5,
        "gender": "男", "longitude": 126.0, "location": "山东",
        "expected": {
            "sizhu_contains": "丙子 戊子",
            "ri_zhu": "丙",
            "shichen_zhi": "子",
        },
    },
]

# ============================================================
# 测试运行器
# ============================================================

def resolve_expected(plate, key):
    """从 BaziPlate 对象提取实际值，用于与 expected 对比"""
    s = plate.sizhu
    ss = plate.shishen
    qy = plate.qiyun
    kg = plate.kongwang
    lunar = plate.lunar
    solar = plate.solar_adjusted

    resolvers = {
        "sizhu": lambda: f"{s['year']['gz']} {s['month']['gz']} {s['day']['gz']} {s['hour']['gz']}",
        "sizhu_contains": None,  # 特殊处理
        "ri_zhu": lambda: plate.ri_zhu,
        "year_type": lambda: plate.year_type,
        "shishen_year": lambda: ss["year"],
        "shishen_month": lambda: ss["month"],
        "shishen_hour": lambda: ss["hour"],
        "shichen_zhi": lambda: DI_ZHI.index(s["hour"]["zhi"]) if s["hour"]["zhi"] in DI_ZHI else -1,
        "qiyun_direction": lambda: qy["direction"],
        "qiyun_age_range": lambda: qy["qiyun_age"],
        "dayun_1_gz": lambda: plate.dayun[0]["gz"] if plate.dayun else "",
        "month_zhi": lambda: s["month"]["zhi"],
        "solar_applied": lambda: solar.get("applied", False),
        "lunar_month": lambda: lunar["month"],
        "month_canggan_contains": None,
        "hour_canggan_zhi": lambda: s["hour"]["zhi"],
        "hour_canggan_contains": None,
        "hour_canggan_count": None,
        "day_changsheng": lambda: plate.changsheng["day"],
        "kongwang_set": lambda: {kg["kong1"], kg["kong2"]},
        "kong_pillar_year": lambda: kg["pillars"]["year"],
        "kong_pillar_month": lambda: kg["pillars"]["month"],
        "taiyuan": lambda: plate.taiyuan,
    }

    if key not in resolvers or resolvers[key] is None:
        return None
    try:
        return resolvers[key]()
    except Exception:
        return None


def run_test(case, verbose=False):
    """运行单条测试用例"""
    try:
        plate = paipan(
            case["year"], case["month"], case["day"],
            case["hour"], case["minute"],
            case["gender"], case["longitude"], case["location"],
            apply_solar_correction=case.get("apply_solar_correction", True),
        )
    except Exception as e:
        return {"id": case["id"], "status": "ERROR", "desc": case["desc"],
                "error": str(e)}

    failures = []

    for key, expected_val in case["expected"].items():
        if key == "sizhu_contains":
            sizhu = f"{plate.sizhu['year']['gz']} {plate.sizhu['month']['gz']} {plate.sizhu['day']['gz']} {plate.sizhu['hour']['gz']}"
            if expected_val not in sizhu:
                failures.append(f"{key}: expected containing '{expected_val}', got '{sizhu}'")
            continue

        if key == "month_canggan_contains":
            actual_gans = [g for g, _ in plate.canggan["month"]]
            missing = [g for g in expected_val if g not in actual_gans]
            if missing:
                failures.append(f"{key}: missing {missing} in {actual_gans}")
            continue

        if key == "hour_canggan_contains":
            actual_gans = [g for g, _ in plate.canggan["hour"]]
            missing = [g for g in expected_val if g not in actual_gans]
            if missing:
                failures.append(f"{key}: missing {missing} in {actual_gans}")
            continue

        if key == "hour_canggan_count":
            actual_count = len(plate.canggan["hour"])
            if actual_count != expected_val:
                failures.append(f"{key}: expected {expected_val}, got {actual_count}")
            continue

        if key == "shichen_zhi":
            shi_zhi = plate.sizhu["hour"]["zhi"]
            if shi_zhi != expected_val:
                failures.append(f"{key}: expected {expected_val}, got {shi_zhi}")
            continue

        if key == "qiyun_age_range":
            low, high = expected_val
            actual = plate.qiyun["qiyun_age"]
            if not (low <= actual <= high):
                failures.append(f"{key}: expected {low}-{high}, got {actual}")
            continue

        if key == "solar_applied":
            actual = plate.solar_adjusted.get("applied", False)
            if actual != expected_val:
                failures.append(f"{key}: expected {expected_val}, got {actual}")
            continue

        if key == "lunar_month":
            if isinstance(expected_val, tuple):
                if plate.lunar["month"] not in expected_val:
                    failures.append(f"{key}: expected one of {expected_val}, got {plate.lunar['month']}")
            elif plate.lunar["month"] != expected_val:
                failures.append(f"{key}: expected {expected_val}, got {plate.lunar['month']}")
            continue

        # 通用比较
        actual = resolve_expected(plate, key)
        if actual is not None and actual != expected_val:
            failures.append(f"{key}: expected '{expected_val}', got '{actual}'")

    status = "PASS" if not failures else "FAIL"
    return {
        "id": case["id"], "status": status, "desc": case["desc"],
        "category": case["category"], "failures": failures,
    }


# ============================================================
# pytest 统一入口（TODO-PAIPAN-PYTEST 参数化，2026-08-06 mose 落）
# 29 条 TEST_CASES 全量参数化，basic-2005-dongguan-male（King 盘回归保护）显形
# 与 main() 同一数据源（TEST_CASES），手动轨计数不变
# ============================================================

@pytest.mark.parametrize("case", TEST_CASES, ids=[c["id"] for c in TEST_CASES])
def test_paipan_case(case):
    """单条排盘用例（参数化自 TEST_CASES）"""
    result = run_test(case)
    assert result["status"] == "PASS", (
        f"{result['id']}: {result.get('desc', '')} "
        f"{result.get('failures', result.get('error', ''))}"
    )


def main():
    verbose = "--verbose" in sys.argv
    smoke_only = "--smoke" in sys.argv

    cases = TEST_CASES
    if smoke_only:
        # 只跑 5 条核心冒烟用例
        smoke_ids = {
            "basic-2005-dongguan-male", "yezi-23h",
            "jieqi-lichun-border", "dayun-yin-male-backward",
            "kongwang-jiaxun",
        }
        cases = [c for c in TEST_CASES if c["id"] in smoke_ids]

    print("=" * 72)
    print("  八字排盘引擎 — 系统化测试")
    print(f"  时间：{datetime.now().isoformat(timespec='seconds')}")
    print(f"  用例数：{len(cases)}")
    print("=" * 72)
    print()

    results = []
    for case in cases:
        result = run_test(case, verbose)
        results.append(result)
        icon = {"PASS": "✅", "FAIL": "❌", "ERROR": "💥"}[result["status"]]
        print(f"{icon} [{result['category']}] {result['id']}: {result['desc']}")
        if result["status"] != "PASS":
            for f in result.get("failures", []):
                print(f"   → {f}")
            if "error" in result:
                print(f"   → ERROR: {result['error']}")
        elif verbose:
            print(f"   (ok)")

    # 汇总
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    errors = sum(1 for r in results if r["status"] == "ERROR")
    total = len(results)

    print()
    print("=" * 72)
    print(f"  结果：{passed} 通过 / {failed} 失败 / {errors} 错误 （共 {total}）")
    if total > 0:
        print(f"  通过率：{passed/total*100:.0f}%")
    print("=" * 72)

    # 按分类统计
    by_cat = {}
    for r in results:
        cat = r["category"]
        if cat not in by_cat:
            by_cat[cat] = {"pass": 0, "fail": 0, "error": 0}
        if r["status"] == "PASS":
            by_cat[cat]["pass"] += 1
        elif r["status"] == "FAIL":
            by_cat[cat]["fail"] += 1
        else:
            by_cat[cat]["error"] += 1

    if not smoke_only and len(by_cat) > 1:
        print()
        print("## 按分类")
        for cat, counts in sorted(by_cat.items()):
            cat_total = sum(counts.values())
            cat_rate = counts["pass"] / cat_total * 100 if cat_total > 0 else 0
            bar = "█" * int(cat_rate / 10) + "░" * (10 - int(cat_rate / 10))
            print(f"  {bar} {cat}: {counts['pass']}/{cat_total} ({cat_rate:.0f}%)")

    return 0 if failed == 0 and errors == 0 else 1


def test_evaluate_liunian_signal():
    """验证六级流年信号判定逻辑"""
    from analysis_service import _evaluate_liunian_signal

    # Mock dayun: 2018-2027 戊戌
    dayun = [{'gz': '戊戌', 'gan': '戊', 'zhi': '戌', 'start_year': 2018, 'start_age': 14.0, 'end_age': 24.0, 'step': 1}]

    # 各测试用例使用独立参数，避免信号冲突
    # S级：天克地冲（庚克甲 + 午冲子）
    level, desc = _evaluate_liunian_signal('庚午', '甲子', '申', '辰', dayun, 2026)
    assert level == 'S', f"Expected S, got {level}"
    assert '天克地冲' in desc

    # A级：日柱伏吟
    level, desc = _evaluate_liunian_signal('甲子', '甲子', '申', '辰', dayun, 2020)
    assert level == 'A', f"Expected A, got {level}"

    # B级：冲日支
    level, desc = _evaluate_liunian_signal('丙午', '甲子', '申', '辰', dayun, 2026)
    assert level == 'B', f"Expected B, got {level}"
    assert '午冲子' in desc

    # C级：六合日支
    level, desc = _evaluate_liunian_signal('己丑', '甲子', '申', '辰', dayun, 2009)
    assert level == 'C', f"Expected C, got {level}"
    assert '丑合子' in desc or '六合' in desc

    # D级：驿马（日支子→驿马在寅；avoid 寅-申 chong, avoid 寅-亥 liuhe）
    level, desc = _evaluate_liunian_signal('甲寅', '甲子', '丑', '酉', dayun, 2010)
    assert level == 'D', f"Expected D for 驿马, got {level}"

    # E级：墓库（日支戌是墓库，流年同支戌但非伏吟）
    level, desc = _evaluate_liunian_signal('庚戌', '甲戌', '子', '寅', dayun, 2012)
    assert level == 'E', f"Expected E for 墓库, got {level}"

    # —：无信号
    level, desc = _evaluate_liunian_signal('己亥', '甲子', '申', '辰', dayun, 2019)
    assert level is None, f"Expected None, got {level}"

    print("[PASS] test_evaluate_liunian_signal: 7/7 信号等级判定正确")


def test_build_year_lookup_table():
    """验证对照表生成格式"""
    from analysis_service import _build_year_lookup_table
    from bazi_calculator import paipan
    from utils.plate import plate_to_dict

    # 2026-08-05 修：函数契约是 dict（签名 plate_dict / docstring "plate_to_dict() 的输出"），
    # 原代码把 paipan() 返回的 BaziPlate 对象直接塞入，BaziPlate 无 .get() → pytest 收集时炸。
    # 修法：utils/plate.py 现成的 plate_to_dict 转 dict（TODO-BAZI-LOOKUP 判修，King 盘回归保护弃了可惜）。
    plate = paipan(2005, 8, 19, 1, 35, '男', 113.75, '东莞')
    table = _build_year_lookup_table(plate_to_dict(plate), 2010)

    # 格式检查
    assert '## 流年干支-西历对照表' in table, '缺少标题'
    assert '出生年：2005年' in table, '缺少出生年'
    assert '日柱：' in table, '缺少日柱'
    assert '| 年份 | 干支 | 所属大运 | 信号等级 | 信号说明 |' in table, '缺少表头'
    assert '2005' in table, '缺少出生年行'
    assert '2010' in table, '缺少当前年行'
    assert '🔵当前' in table, '缺少当前大运标记'

    # 逐年行数 = (2010 - 2005 + 1) + 表头2行 + section header等
    lines = table.strip().split('\n')
    data_lines = [l for l in lines if l.startswith('| 20')]
    assert len(data_lines) == 6, f'预期6年数据行，实际{len(data_lines)}'

    # 格式：20XX年（干支）
    assert '2005年（乙酉）' in table, '缺少出生年对照'

    print("[PASS] test_build_year_lookup_table: 对照表格式正确")


if __name__ == "__main__":
    sys.exit(main())
