#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""八字排盘精确计算模块

基于 sxtwl (寿星天文历) 进行精确的八字排盘计算:
  - 四柱干支 (年月日时)
  - 真太阳时校正
  - 起运时间 (精确到天)
  - 大运排列 (顺行/逆行)
  - 空亡、纳音、藏干
  - 十神关系
  - 十二长生
  - 胎元、命宫、身宫
  - 节气/农历信息
"""

from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

# 优先使用 sxtwl（C++ 高精度），不可用时回退到内嵌纯 Python 方案
try:
    import sxtwl
    _USE_SXTWL = True
except ImportError:
    sxtwl = None
    _USE_SXTWL = False
    from datetime import date as _fd, timedelta as _ft
    import math as _math
    try:
        from zhdate import ZhDate
    except ImportError:
        ZhDate = None

    _RD = _fd(2000, 1, 1)
    _RG, _RZ = 4, 6

    # 节索引（小寒=1, 立春=3, 惊蛰=5, ... 大雪=23）→ 月支（寅=2）
    _JIE_TO_MONTH = {1:12, 3:1, 5:2, 7:3, 9:4, 11:5, 13:6, 15:7, 17:8, 19:9, 21:10, 23:11}
    # 月数→地支：寅=2, 卯=3, ..., 子=0, 丑=1
    _MONTH_ZHI = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 0, 1]

    # ---- 纯数学节气计算（Meeus 天文算法简化 + 缓存） ----
    _ST_CACHE = {}  # (year, idx) → JD，预计算后缓存

    def _sun_lon(jd: float) -> float:
        """太阳视黄经 (degrees)，含章动修正，精度 ~0.001°"""
        T = (jd - 2451545.0) / 36525.0
        L0 = (280.46646 + 36000.76983 * T + 0.0003032 * T * T) % 360
        M = (357.52911 + 35999.05029 * T - 0.0001537 * T * T) % 360
        Mr = _math.radians(M)
        C = (1.914602 - 0.004817 * T - 0.000014 * T * T) * _math.sin(Mr) \
            + (0.019993 - 0.000101 * T) * _math.sin(2 * Mr) \
            + 0.000289 * _math.sin(3 * Mr)
        # 章动近似（经度项，~0.004°）
        omega = _math.radians(125.04 - 1934.136 * T)
        nutation = 0.0041 * _math.sin(omega)
        return (L0 + C + nutation) % 360

    def _st_jd(year: int, idx: int) -> float:
        """计算第 idx 个节气的 Julian Day。先查缓存，未命中再计算。"""
        key = (year, idx)
        if key in _ST_CACHE:
            return _ST_CACHE[key]
        target = (idx * 15 + 270) % 360
        winter_jd_2000 = 2451900.6
        guess = winter_jd_2000 + (year - 2000) * 365.2422 + idx * 15.2184
        for _ in range(10):
            lon = _sun_lon(guess)
            diff = (target - lon + 180.0) % 360.0 - 180.0
            if abs(diff) < 0.00001:
                break
            guess += diff / 0.9856
        _ST_CACHE[key] = guess
        return guess

    def _preload_terms(years: set):
        """预加载指定年份的全部 24 个节气（并行填充缓存）"""
        for y in years:
            for i in range(24):
                _st_jd(y, i)

    class _GZ:
        __slots__ = ('tg', 'dz')
        def __init__(s, tg, dz): s.tg = tg; s.dz = dz

    class _Day:
        def __init__(s, y, m, d):
            s.year, s.month, s.day = y, m, d
            s._dt = _fd(y, m, d)
            o = (y - 4) % 60; yg = o % 10
            s._ygz = _GZ(yg, o % 12)

            # 预加载三年节气缓存（首次排盘时一次性计算，后续全部命中）
            _preload_terms({y - 1, y, y + 1})

            # 月柱：根据节气确定（精确）
            # 查找出生日期之前最近的"节"
            jd0 = 2451545.0 + (s._dt - _fd(2000, 1, 1)).days
            prev_jie = 1  # 默认小寒
            best_jd = None
            for idx in _JIE_TO_MONTH:
                jd = _st_jd(y, idx)
                if jd <= jd0 and (best_jd is None or jd > best_jd):
                    best_jd = jd
                    prev_jie = idx
                # 也检查上一年的大雪(23)
                jd_prev = _st_jd(y - 1, idx)
                if jd_prev <= jd0 and (best_jd is None or jd_prev > best_jd):
                    best_jd = jd_prev
                    prev_jie = idx
            month_num = _JIE_TO_MONTH.get(prev_jie, 2)
            mz = _MONTH_ZHI[month_num]

            # 月干：五虎遁（甲己之年丙作首）
            b = {0: 2, 5: 2, 1: 4, 6: 4, 2: 6, 7: 6, 3: 8, 8: 8, 4: 0, 9: 0}
            s._mgz = _GZ((b[yg] + month_num - 1) % 10, mz)

            dl = (s._dt - _RD).days
            s._dgz = _GZ((_RG + dl) % 10, (_RZ + dl) % 12)
            s._ly = s._lm = s._ld = 0; s._lp = False
            if ZhDate:
                try:
                    from datetime import datetime as _dtt
                    l = ZhDate.from_datetime(_dtt(y, m, d))
                    s._ly, s._lm, s._ld = l.lunar_year, l.lunar_month, l.lunar_day
                    s._lp = (l.leap_month is not None and l.lunar_month == l.leap_month)
                except Exception:
                    pass

        def getYearGZ(s): return s._ygz
        def getMonthGZ(s): return s._mgz
        def getDayGZ(s): return s._dgz
        def getLunarYear(s): return s._ly
        def getLunarMonth(s): return s._lm
        def getLunarDay(s): return s._ld
        def isLunarLeap(s): return s._lp

        def _jd(s): return 2451545.0 + (s._dt - _fd(2000, 1, 1)).days

        def _find_jieqi_jd(s) -> float | None:
            """返回当天节气的 JD，无则返回 None。找最近节气（前后 12 小时内）。"""
            j0 = s._jd()
            for y in (s.year - 1, s.year, s.year + 1):
                for i in range(24):
                    jd = _st_jd(y, i)
                    if abs(jd - j0) < 0.5:
                        return jd
            return None

        def hasJieQi(s):
            return s._find_jieqi_jd() is not None

        def getJieQiJD(s):
            found = s._find_jieqi_jd()
            if found is not None:
                return found
            # 回退：找最近的下一个节气
            j0 = s._jd(); best = None; bd = float('inf')
            for y in (s.year - 1, s.year, s.year + 1):
                for i in range(24):
                    j = _st_jd(y, i)
                    df = j - j0
                    if df > 0 and df < bd:
                        bd = df; best = j
            return best or j0

        def after(s, days):
            nd = s._dt + _ft(days=days)
            return _Day(nd.year, nd.month, nd.day)

        def before(s, days):
            nd = s._dt - _ft(days=days)
            return _Day(nd.year, nd.month, nd.day)

    def _fromSolar_fallback(y, m, d):
        return _Day(y, m, d)

# sxtwl 可用时 _fromSolar_fallback 未定义，提供一个空实现
if _USE_SXTWL:
    def _fromSolar_fallback(y, m, d):
        return None

# ============================================================
# 常量表
# ============================================================

TIAN_GAN = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸']
DI_ZHI = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥']

# 五行属性: 0=木, 1=火, 2=土, 3=金, 4=水
WU_XING_MAP = {
    '甲': 0, '乙': 0,  # 木
    '丙': 1, '丁': 1,  # 火
    '戊': 2, '己': 2,  # 土
    '庚': 3, '辛': 3,  # 金
    '壬': 4, '癸': 4,  # 水
}
WU_XING_NAME = ['木', '火', '土', '金', '水']

# 天干阴阳: True=阳, False=阴
GAN_YIN_YANG = {
    '甲': True, '乙': False,
    '丙': True, '丁': False,
    '戊': True, '己': False,
    '庚': True, '辛': False,
    '壬': True, '癸': False,
}

# 地支藏干 (本气/中气/余气, 比例为近似值)
CANG_GAN = {
    '子': [('癸', 1.0)],
    '丑': [('己', 0.5), ('癸', 0.3), ('辛', 0.2)],
    '寅': [('甲', 0.5), ('丙', 0.3), ('戊', 0.2)],
    '卯': [('乙', 1.0)],
    '辰': [('戊', 0.5), ('乙', 0.3), ('癸', 0.2)],
    '巳': [('丙', 0.5), ('戊', 0.3), ('庚', 0.2)],
    '午': [('丁', 0.5), ('己', 0.3)],
    '未': [('己', 0.5), ('丁', 0.3), ('乙', 0.2)],
    '申': [('庚', 0.5), ('壬', 0.3), ('戊', 0.2)],
    '酉': [('辛', 1.0)],
    '戌': [('戊', 0.5), ('辛', 0.3), ('丁', 0.2)],
    '亥': [('壬', 0.5), ('甲', 0.3)],
}

# 纳音表 (60甲子)
NAYIN_TABLE = {
    '甲子': '海中金', '乙丑': '海中金',
    '丙寅': '炉中火', '丁卯': '炉中火',
    '戊辰': '大林木', '己巳': '大林木',
    '庚午': '路旁土', '辛未': '路旁土',
    '壬申': '剑锋金', '癸酉': '剑锋金',
    '甲戌': '山头火', '乙亥': '山头火',
    '丙子': '涧下水', '丁丑': '涧下水',
    '戊寅': '城头土', '己卯': '城头土',
    '庚辰': '白蜡金', '辛巳': '白蜡金',
    '壬午': '杨柳木', '癸未': '杨柳木',
    '甲申': '泉中水', '乙酉': '泉中水',
    '丙戌': '屋上土', '丁亥': '屋上土',
    '戊子': '霹雳火', '己丑': '霹雳火',
    '庚寅': '松柏木', '辛卯': '松柏木',
    '壬辰': '长流水', '癸巳': '长流水',
    '甲午': '沙中金', '乙未': '沙中金',
    '丙申': '山下火', '丁酉': '山下火',
    '戊戌': '平地木', '己亥': '平地木',
    '庚子': '壁上土', '辛丑': '壁上土',
    '壬寅': '金箔金', '癸卯': '金箔金',
    '甲辰': '覆灯火', '乙巳': '覆灯火',
    '丙午': '天河水', '丁未': '天河水',
    '戊申': '大驿土', '己酉': '大驿土',
    '庚戌': '钗钏金', '辛亥': '钗钏金',
    '壬子': '桑柘木', '癸丑': '桑柘木',
    '甲寅': '大溪水', '乙卯': '大溪水',
    '丙辰': '沙中土', '丁巳': '沙中土',
    '戊午': '天上火', '己未': '天上火',
    '庚申': '石榴木', '辛酉': '石榴木',
    '壬戌': '大海水', '癸亥': '大海水',
}

CHANG_SHENG_ORDER = ['长生', '沐浴', '冠带', '临官', '帝旺', '衰', '病', '死', '墓', '绝', '胎', '养']

# 阳干长生位: 甲亥, 丙寅, 戊寅, 庚巳, 壬申
# 阳干长生位: 甲亥, 丙寅, 戊寅, 庚巳, 壬申
YANG_CHANGSHENG = {
    '甲': 11,  # 亥 (甲木长生在亥)
    '丙': 2,   # 寅 (丙火长生在寅)
    '戊': 2,   # 寅 (戊从丙)
    '庚': 5,   # 巳 (庚金长生在巳)
    '壬': 8,   # 申 (壬水长生在申)
}
# 阴干长生位 = 阳干死位 (阳干长生+6 mod 12)
# 乙=午(6), 丁=酉(9), 己=酉(9), 辛=子(0), 癸=卯(3)


def _get_changsheng(day_gan: str, dz: str) -> str:
    """查十二长生"""
    dz_idx = DI_ZHI.index(dz)
    is_yang = GAN_YIN_YANG[day_gan]

    if is_yang:
        # 阳干: 从长生位顺时针
        gan_wu = WU_XING_MAP[day_gan]
        yang_gan = TIAN_GAN[gan_wu * 2]  # 找到同五行的阳干
        start = YANG_CHANGSHENG[yang_gan]
        offset = (dz_idx - start) % 12
        return CHANG_SHENG_ORDER[offset]
    else:
        # 阴干: 从长生位逆时针 = 阳干死位逆数
        gan_wu = WU_XING_MAP[day_gan]
        yang_gan = TIAN_GAN[gan_wu * 2]
        yang_start = YANG_CHANGSHENG[yang_gan]
        # 阴干长生 = 阳干死位
        yin_start = (yang_start + 7) % 12  # 阴干长生=阳干死位 (长生+7)
        # 从阴长生位逆数
        offset = (yin_start - dz_idx) % 12
        return CHANG_SHENG_ORDER[offset]


def _solar_day(year: int, month: int, day: int):
    """统一入口：公历→sxtwl Day 对象（自动回退）"""
    if _USE_SXTWL:
        return sxtwl.fromSolar(year, month, day)
    else:
        return _fromSolar_fallback(year, month, day)


# ============================================================
# 计算函数
# ============================================================

def gan_he(gz1: str, gz2: str) -> bool:
    """天干五合: 甲己合, 乙庚合, 丙辛合, 丁壬合, 戊癸合"""
    he_pairs = {('甲', '己'), ('乙', '庚'), ('丙', '辛'), ('丁', '壬'), ('戊', '癸')}
    g1, g2 = gz1[0], gz2[0]
    return (g1, g2) in he_pairs or (g2, g1) in he_pairs


def di_liuhe(z1: str, z2: str) -> bool:
    """地支六合: 子丑合, 寅亥合, 卯戌合, 辰酉合, 巳申合, 午未合"""
    he_pairs = {('子', '丑'), ('寅', '亥'), ('卯', '戌'), ('辰', '酉'), ('巳', '申'), ('午', '未')}
    return (z1, z2) in he_pairs or (z2, z1) in he_pairs


def di_sanhe(dz1: str, dz2: str, dz3: str) -> Optional[str]:
    """地支三合: 申子辰→水, 亥卯未→木, 寅午戌→火, 巳酉丑→金"""
    sets = {
        frozenset(['申', '子', '辰']): '水',
        frozenset(['亥', '卯', '未']): '木',
        frozenset(['寅', '午', '戌']): '火',
        frozenset(['巳', '酉', '丑']): '金',
    }
    key = frozenset([dz1, dz2, dz3])
    return sets.get(key)


def di_banhe(dz1: str, dz2: str) -> Optional[str]:
    """地支半合: 生旺半合或旺墓半合"""
    pairs = {
        frozenset(['申', '子']): '水', frozenset(['子', '辰']): '水',
        frozenset(['亥', '卯']): '木', frozenset(['卯', '未']): '木',
        frozenset(['寅', '午']): '火', frozenset(['午', '戌']): '火',
        frozenset(['巳', '酉']): '金', frozenset(['酉', '丑']): '金',
    }
    return pairs.get(frozenset([dz1, dz2]))


def di_liuhai(dz1: str, dz2: str) -> bool:
    """地支六害"""
    hai_pairs = {
        ('子', '未'), ('丑', '午'), ('寅', '巳'),
        ('卯', '辰'), ('申', '亥'), ('酉', '戌'),
    }
    return (dz1, dz2) in hai_pairs or (dz2, dz1) in hai_pairs


def di_liuchong(dz1: str, dz2: str) -> bool:
    """地支六冲: 子午冲, 丑未冲, 寅申冲, 卯酉冲, 辰戌冲, 巳亥冲"""
    chong_pairs = {('子', '午'), ('丑', '未'), ('寅', '申'), ('卯', '酉'), ('辰', '戌'), ('巳', '亥')}
    return (dz1, dz2) in chong_pairs or (dz2, dz1) in chong_pairs


def di_xing(dz1: str, dz2: str) -> Optional[str]:
    """地支相刑, 返回刑的类型"""
    xing_map = {
        ('寅', '巳'): '无恩之刑(寅刑巳)',
        ('巳', '申'): '无恩之刑(巳刑申)',
        ('申', '寅'): '无恩之刑(申刑寅)',
        ('丑', '戌'): '恃势之刑(丑刑戌)',
        ('戌', '未'): '恃势之刑(戌刑未)',
        ('未', '丑'): '恃势之刑(未刑丑)',
        ('子', '卯'): '无礼之刑',
    }
    # 双向
    result = xing_map.get((dz1, dz2))
    if result:
        return result
    result = xing_map.get((dz2, dz1))
    if result:
        return result
    # 自刑
    if dz1 == dz2 and dz1 in ('辰', '午', '酉', '亥'):
        return f'自刑({dz1})'
    return None


def get_shishen(ri_gan: str, target_gan: str) -> str:
    """十神: 日干与其他天干的关系"""
    ri_wu = WU_XING_MAP[ri_gan]
    tgt_wu = WU_XING_MAP[target_gan]
    ri_yy = GAN_YIN_YANG[ri_gan]
    tgt_yy = GAN_YIN_YANG[target_gan]

    same_yy = (ri_yy == tgt_yy)

    if ri_wu == tgt_wu:
        return '比肩' if same_yy else '劫财'
    # 生克关系: 木→火→土→金→水→木
    ri_sheng = (ri_wu + 1) % 5  # 日干生的五行
    ri_ke = (ri_wu + 2) % 5     # 日干克的五行
    ke_ri = (ri_wu + 3) % 5     # 克日干的五行 (金克木 when 金=3, 木=0)

    if tgt_wu == ri_sheng:
        return '食神' if same_yy else '伤官'
    if tgt_wu == ri_ke:
        return '偏财' if same_yy else '正财'
    if tgt_wu == ke_ri:
        return '七杀' if same_yy else '正官'
    # 生日干的
    sheng_ri = (ri_wu + 4) % 5
    if tgt_wu == sheng_ri:
        return '偏印' if same_yy else '正印'

    return '未知'


def get_nayin(gz: str) -> str:
    """纳音"""
    return NAYIN_TABLE.get(gz, '')


def get_kongwang(ri_gan: str, ri_zhi: str) -> Tuple[str, str]:
    """日柱旬空: 返回空亡的两个地支"""
    # 60甲子顺序
    gz_list = [TIAN_GAN[i % 10] + DI_ZHI[i % 12] for i in range(60)]
    idx = gz_list.index(ri_gan + ri_zhi)
    # 所在旬的起始
    xun_start = (idx // 10) * 10
    # 该旬10个干支用到的地支
    used_dz = set()
    for i in range(xun_start, xun_start + 10):
        used_dz.add(gz_list[i][1])
    # 空亡 = 未出现的地支 (每旬缺2个)
    kong = [dz for dz in DI_ZHI if dz not in used_dz]
    return kong[0], kong[1]


def _wushu_dun(day_gan: str, shi_idx: int) -> int:
    """五鼠遁: 根据日干和时辰序号(子=0)返回时干index"""
    wushu_group = {'甲': 0, '己': 0, '乙': 1, '庚': 1, '丙': 2, '辛': 2,
                   '丁': 3, '壬': 3, '戊': 4, '癸': 4}
    start_gan = (wushu_group[day_gan] * 2) % 10
    return (start_gan + shi_idx) % 10


def calc_sizhu(year: int, month: int, day: int, hour: int, minute: int = 0) -> dict:
    """计算四柱"""
    sxt_day = _solar_day(year, month, day)

    # 确定时辰地支
    if hour == 23 or hour == 0:
        shi_idx = 0  # 子
    else:
        shi_idx = ((hour - 1) // 2 + 1) % 12  # 丑=1, 寅=2, ...

    shi_zhi = DI_ZHI[shi_idx]

    # 年/月/日柱: 直接从sxtwl获取 (sxtwl对公历日期的干支计算是可靠的)
    ygz = sxt_day.getYearGZ()
    mgz = sxt_day.getMonthGZ()
    dgz = sxt_day.getDayGZ()

    # 夜子时(23:00-23:59): 日柱已进入次日, 时柱按次日日干起五鼠遁
    is_yezi = (hour == 23)
    if is_yezi:
        next_day = sxt_day.after(1)
        ndgz = next_day.getDayGZ()
        day_gan_for_hour = TIAN_GAN[ndgz.tg]
        # 日柱也使用次日
        day_gan = day_gan_for_hour
        day_zhi = DI_ZHI[ndgz.dz]
        day_gz = day_gan + day_zhi
    else:
        day_gan_for_hour = TIAN_GAN[dgz.tg]
        day_gan = day_gan_for_hour
        day_zhi = DI_ZHI[dgz.dz]
        day_gz = day_gan + day_zhi

    # 时干: 用五鼠遁 (不依赖sxtwl的getHourGZ, 因其有时区bug)
    hour_gan = TIAN_GAN[_wushu_dun(day_gan_for_hour, shi_idx)]
    hour_gz = hour_gan + shi_zhi

    return {
        'year':  {'gan': TIAN_GAN[ygz.tg], 'zhi': DI_ZHI[ygz.dz], 'gz': TIAN_GAN[ygz.tg] + DI_ZHI[ygz.dz]},
        'month': {'gan': TIAN_GAN[mgz.tg], 'zhi': DI_ZHI[mgz.dz], 'gz': TIAN_GAN[mgz.tg] + DI_ZHI[mgz.dz]},
        'day':   {'gan': day_gan, 'zhi': day_zhi, 'gz': day_gz},
        'hour':  {'gan': hour_gan, 'zhi': shi_zhi, 'gz': hour_gz},
    }


def calc_true_solar_time(birth_utc_hour: float, longitude: float) -> dict:
    """真太阳时校正

    Args:
        birth_utc_hour: UTC 出生时间的小时部分
        longitude: 经度 (东经为正)

    Returns:
        dict with correction in minutes and adjusted time
    """
    # 平太阳时: 时区中心经度 - 本地经度
    # 北京时间 = UTC+8, 时区中心经度 = 120°E
    timezone_center = 120.0
    # 每度差4分钟
    correction = (longitude - timezone_center) * 4.0
    # 真太阳时 = 平太阳时 + 均时差(近似忽略) + 经度修正
    return {
        'correction_minutes': round(correction, 1),
        'adjusted_hour': birth_utc_hour + 8 + correction / 60,
    }


def _to_jd(dt: datetime) -> float:
    """datetime(UTC) → Julian Day"""
    epoch = datetime(2000, 1, 1, 12, 0, tzinfo=timezone.utc)
    delta = dt - epoch
    return 2451545.0 + delta.total_seconds() / 86400.0


def calc_qiyun(birth_dt: datetime, is_yang_year: bool, is_male: bool,
               longitude: float = 120.0) -> dict:
    """计算起运时间

    阳年男/阴年女 → 顺行 (数到下一个节气)
    阴年男/阳年女 → 逆行 (数到上一个节气)

    3天 = 1岁起运
    """
    sxt_day = _solar_day(birth_dt.year, birth_dt.month, birth_dt.day)

    # 判断顺逆行
    if is_yang_year:
        forward = is_male  # 阳年男顺, 阳年女逆
    else:
        forward = not is_male  # 阴年女顺, 阴年男逆

    # 出生时刻 JD（北京时区 UTC+8）
    if birth_dt.tzinfo is None:
        birth_dt_beijing = birth_dt.replace(tzinfo=timezone(timedelta(hours=8)))
    else:
        birth_dt_beijing = birth_dt
    birth_utc = birth_dt_beijing.astimezone(timezone.utc)
    birth_jd = _to_jd(birth_utc)

    # 找到相邻节气
    # 从出生日向前/后搜索节气
    jq_jd = None
    if forward:
        # 顺行: 向后找下一个节气 (after birth)
        for offset in range(1, 35):
            cursor = sxt_day.after(offset)
            if cursor.hasJieQi():
                jq_jd = cursor.getJieQiJD()
                break
    else:
        # 逆行: 向前找上一个节气 (before birth)
        for offset in range(1, 35):
            cursor = sxt_day.before(offset)
            if cursor.hasJieQi():
                jq_jd = cursor.getJieQiJD()
                break

    if jq_jd is None:
        raise ValueError('未找到相邻节气')

    diff_days = abs(birth_jd - jq_jd)
    qiyun_age = diff_days / 3.0
    qiyun_year = birth_dt.year + qiyun_age

    # 虚岁起运 (向上取整)
    qiyun_age_xu = int(qiyun_age + 0.99)

    return {
        'forward': forward,
        'jie_qi_jd': jq_jd,
        'birth_jd': birth_jd,
        'diff_days': round(diff_days, 2),
        'qiyun_age': round(qiyun_age, 2),
        'qiyun_age_xu': qiyun_age_xu,
        'qiyun_year': round(qiyun_year, 1),
        'direction': '顺行' if forward else '逆行',
    }


def calc_dayun(yue_gan: str, yue_zhi: str, forward: bool,
               qiyun_age: float, num_steps: int = 8) -> list:
    """排大运

    Args:
        yue_gan: 月干
        yue_zhi: 月支
        forward: True=顺行(干支向后推), False=逆行(干支向前推)
        qiyun_age: 起运年龄
        num_steps: 大运步数

    Returns:
        [(干支, 起运年龄, 结束年龄, 步数), ...]
    """
    gan_idx = TIAN_GAN.index(yue_gan)
    zhi_idx = DI_ZHI.index(yue_zhi)

    result = []
    current_age = qiyun_age

    for step in range(num_steps):
        if forward:
            gan_idx = (gan_idx + 1) % 10
            zhi_idx = (zhi_idx + 1) % 12
        else:
            gan_idx = (gan_idx - 1) % 10
            zhi_idx = (zhi_idx - 1) % 12

        gz = TIAN_GAN[gan_idx] + DI_ZHI[zhi_idx]
        start_age = current_age
        end_age = start_age + 10
        result.append({
            'gz': gz,
            'gan': TIAN_GAN[gan_idx],
            'zhi': DI_ZHI[zhi_idx],
            'step': step + 1,
            'start_age': round(start_age, 1),
            'end_age': round(end_age, 1),
            'start_year': 0,  # placeholder, caller fills real year
        })
        current_age = end_age

    return result


def calc_lunar_info(year: int, month: int, day: int) -> dict:
    """获取农历信息"""
    sxt_day = _solar_day(year, month, day)
    lunar_y = sxt_day.getLunarYear()
    lunar_m = sxt_day.getLunarMonth()
    lunar_d = sxt_day.getLunarDay()
    is_leap = sxt_day.isLunarLeap()

    return {
        'year': lunar_y,
        'month': lunar_m,
        'day': lunar_d,
        'is_leap': is_leap,
    }


def calc_taiyuan(yue_gan: str, yue_zhi: str) -> str:
    """胎元: 月柱天干顺推一位, 地支顺推三位"""
    gan_idx = (TIAN_GAN.index(yue_gan) + 1) % 10
    zhi_idx = (DI_ZHI.index(yue_zhi) + 3) % 12
    return TIAN_GAN[gan_idx] + DI_ZHI[zhi_idx]


def calc_minggong(yue_zhi: str, shi_zhi: str) -> str:
    """命宫: (14 - 月支数 - 时支数) mod 12

    月支数: 寅=1, 卯=2, ..., 丑=12
    时支数: 子=1, 丑=2, ..., 亥=12
    结果: 子=1, 丑=2, ..., 亥=12
    """
    # 月支编号 (寅=1)
    yue_seq = {'寅': 1, '卯': 2, '辰': 3, '巳': 4, '午': 5, '未': 6,
               '申': 7, '酉': 8, '戌': 9, '亥': 10, '子': 11, '丑': 12}
    # 时支编号 (子=1)
    shi_seq = {'子': 1, '丑': 2, '寅': 3, '卯': 4, '辰': 5, '巳': 6,
               '午': 7, '未': 8, '申': 9, '酉': 10, '戌': 11, '亥': 12}
    # 命宫编号→地支 (子=1)
    ming_seq = {1: '子', 2: '丑', 3: '寅', 4: '卯', 5: '辰', 6: '巳',
                7: '午', 8: '未', 9: '申', 10: '酉', 11: '戌', 12: '亥'}

    val = 14 - yue_seq[yue_zhi] - shi_seq[shi_zhi]
    while val <= 0:
        val += 12
    return ming_seq[val]


def calc_shengong(yue_zhi: str, shi_zhi: str) -> str:
    """身宫: 与命宫对称

    公式: (月支数 + 时支数) mod 12, 月支寅=1, 时支子=1
    结果: 子=1
    """
    yue_seq = {'寅': 1, '卯': 2, '辰': 3, '巳': 4, '午': 5, '未': 6,
               '申': 7, '酉': 8, '戌': 9, '亥': 10, '子': 11, '丑': 12}
    shi_seq = {'子': 1, '丑': 2, '寅': 3, '卯': 4, '辰': 5, '巳': 6,
               '午': 7, '未': 8, '申': 9, '酉': 10, '戌': 11, '亥': 12}
    ming_seq = {1: '子', 2: '丑', 3: '寅', 4: '卯', 5: '辰', 6: '巳',
                7: '午', 8: '未', 9: '申', 10: '酉', 11: '戌', 12: '亥'}

    val = yue_seq[yue_zhi] + shi_seq[shi_zhi]
    if val > 12:
        val -= 12
    return ming_seq[val]


def get_jieqi_name(index: int) -> str:
    """节气序号→名称"""
    names = [
        '冬至', '小寒', '大寒', '立春', '雨水', '惊蛰',
        '春分', '清明', '谷雨', '立夏', '小满', '芒种',
        '夏至', '小暑', '大暑', '立秋', '处暑', '白露',
        '秋分', '寒露', '霜降', '立冬', '小雪', '大雪',
    ]
    return names[index] if 0 <= index < len(names) else f'未知({index})'


# ============================================================
# 综合排盘类
# ============================================================

@dataclass
class BaziPlate:
    """完整八字命盘"""
    # 基本输入
    birth_dt: datetime
    gender: str  # '男' or '女'
    longitude: float = 120.0
    location: str = ''
    birth_dt_original: datetime = None  # 用户输入的原始时间（未校正）

    # 计算后的数据
    solar_adjusted: dict = field(default_factory=dict)
    sizhu: dict = field(default_factory=dict)
    lunar: dict = field(default_factory=dict)
    qiyun: dict = field(default_factory=dict)
    dayun: list = field(default_factory=list)
    shishen: dict = field(default_factory=dict)
    nayin: dict = field(default_factory=dict)
    kongwang: dict = field(default_factory=dict)
    canggan: dict = field(default_factory=dict)
    changsheng: dict = field(default_factory=dict)
    taiyuan: str = ''
    minggong: str = ''
    shengong: str = ''

    # 辅助标记
    ri_zhu: str = ''
    year_type: str = ''  # '阳年' or '阴年'

    def compute(self, solar_pre_applied: float = 0.0):
        """执行所有计算

        Args:
            solar_pre_applied: paipan() 已预先应用的校正（分钟）。0=未应用。
        """
        y, m, d = self.birth_dt.year, self.birth_dt.month, self.birth_dt.day
        h, mi = self.birth_dt.hour, self.birth_dt.minute

        # 1. 真太阳时
        if solar_pre_applied != 0.0:
            # 校正已由 paipan() 应用，存实际校正值用于展示
            self.solar_adjusted = {
                'correction_minutes': solar_pre_applied,
                'adjusted_hour': h + mi / 60,
                'applied': True,
            }
        else:
            utc_hour = h - 8 + mi / 60  # 北京时→UTC
            self.solar_adjusted = calc_true_solar_time(utc_hour, self.longitude)

        # 2. 四柱
        self.sizhu = calc_sizhu(y, m, d, h, mi)

        # 3. 农历
        self.lunar = calc_lunar_info(y, m, d)

        # 4. 日主 & 年柱阴阳
        nian_gan = self.sizhu['year']['gan']
        ri_gan = self.sizhu['day']['gan']
        self.ri_zhu = ri_gan
        nian_is_yang = GAN_YIN_YANG[nian_gan]
        self.year_type = '阳年' if nian_is_yang else '阴年'
        is_male = (self.gender == '男')

        # 5. 十神
        pillars = ['year', 'month', 'hour']
        for p in pillars:
            g = self.sizhu[p]['gan']
            self.shishen[p] = get_shishen(ri_gan, g)
        # 日柱比肩
        self.shishen['day'] = '日主'

        # 6. 纳音
        for p in ['year', 'month', 'day', 'hour']:
            self.nayin[p] = get_nayin(self.sizhu[p]['gz'])

        # 7. 空亡
        kong1, kong2 = get_kongwang(ri_gan, self.sizhu['day']['zhi'])
        self.kongwang = {'kong1': kong1, 'kong2': kong2}
        # 标记各柱是否空亡
        self.kongwang['pillars'] = {}
        for p in ['year', 'month', 'day', 'hour']:
            zhi = self.sizhu[p]['zhi']
            self.kongwang['pillars'][p] = (zhi == kong1 or zhi == kong2)

        # 8. 藏干
        for p in ['year', 'month', 'day', 'hour']:
            zhi = self.sizhu[p]['zhi']
            self.canggan[p] = CANG_GAN.get(zhi, [])

        # 9. 十二长生
        for p in ['year', 'month', 'day', 'hour']:
            self.changsheng[p] = _get_changsheng(ri_gan, self.sizhu[p]['zhi'])

        # 10. 胎元/命宫/身宫
        self.taiyuan = calc_taiyuan(
            self.sizhu['month']['gan'], self.sizhu['month']['zhi'])
        self.minggong = calc_minggong(
            self.sizhu['month']['zhi'], self.sizhu['hour']['zhi'])
        self.shengong = calc_shengong(
            self.sizhu['month']['zhi'], self.sizhu['hour']['zhi'])

        # 11. 起运
        self.qiyun = calc_qiyun(
            self.birth_dt, nian_is_yang, is_male, self.longitude)

        # 12. 大运 — 覆盖到当前年份（至少8步）
        import datetime
        current_year = datetime.datetime.now().year
        steps_needed = max(8, int((current_year - y - self.qiyun['qiyun_age']) / 10) + 2)
        self.dayun = calc_dayun(
            self.sizhu['month']['gan'],
            self.sizhu['month']['zhi'],
            self.qiyun['forward'],
            self.qiyun['qiyun_age'],
            num_steps=steps_needed,
        )
        # 补全起运年份
        for du in self.dayun:
            du['start_year'] = round(y + du['start_age'])
            du['end_year'] = round(y + du['end_age'])

        return self

    def summary(self) -> str:
        """打印命盘摘要"""
        lines = []
        s = self.sizhu
        lines.append(f"四柱:  {s['year']['gz']}  {s['month']['gz']}  {s['day']['gz']}  {s['hour']['gz']}")
        lines.append(f"天干:  {s['year']['gan']}    {s['month']['gan']}    {s['day']['gan']}    {s['hour']['gan']}")
        lines.append(f"地支:  {s['year']['zhi']}    {s['month']['zhi']}    {s['day']['zhi']}    {s['hour']['zhi']}")
        lines.append(f"十神:  {self.shishen['year']}  {self.shishen['month']}  {self.shishen['day']}  {self.shishen['hour']}")
        lines.append(f"纳音:  {self.nayin['year']}  {self.nayin['month']}  {self.nayin['day']}  {self.nayin['hour']}")
        lines.append(f"空亡: {self.kongwang['kong1']}{self.kongwang['kong2']}  "
                     f"年{'Y' if self.kongwang['pillars']['year'] else 'N'} "
                     f"月{'Y' if self.kongwang['pillars']['month'] else 'N'} "
                     f"日{'Y' if self.kongwang['pillars']['day'] else 'N'} "
                     f"时{'Y' if self.kongwang['pillars']['hour'] else 'N'}")
        lines.append(f"日主: {s['day']['gan']}{s['day']['zhi']} ({self.year_type})")
        lines.append(f"胎元: {self.taiyuan}  命宫: {self.minggong}  身宫: {self.shengong}")
        qy = self.qiyun
        lines.append(f"起运: {qy['qiyun_age']}岁 ({qy['direction']}, 约{qy['qiyun_year']:.0f}年交运)")
        lines.append(f"大运: {' → '.join(d['gz'] for d in self.dayun)}")
        return '\n'.join(lines)


# ============================================================
# 便捷接口
# ============================================================

def paipan(year: int, month: int, day: int, hour: int, minute: int = 0,
           gender: str = '男', longitude: float = 113.75,
           location: str = '', apply_solar_correction: bool = True) -> BaziPlate:
    """排盘入口

    Args:
        apply_solar_correction: 是否自动应用真太阳时校正到四柱计算。
            默认 True — 直接调用（测试/PDF/独立使用）时自动校正。
            Flask 路由传 False — 路由层已通过用户参数手动校正。
    """
    dt_user = datetime(year, month, day, hour, minute)  # 用户原始输入，不变
    solar_correction_applied = 0.0
    if apply_solar_correction:
        solar_correction_applied = (longitude - 120.0) * 4.0
        dt_calc = dt_user + timedelta(minutes=solar_correction_applied)
    else:
        dt_calc = dt_user
    plate = BaziPlate(
        birth_dt=dt_calc,
        birth_dt_original=dt_user,
        gender=gender,
        longitude=longitude,
        location=location or '未知',
    )
    plate.compute(solar_pre_applied=solar_correction_applied)
    return plate


# ============================================================
# 测试
# ============================================================

if __name__ == '__main__':
    # 测试: 2005年8月19日 01:35 丑时 男 东莞
    print('=' * 60)
    print('八字排盘计算器 - 验证测试')
    print('=' * 60)
    print()

    plate = paipan(2005, 8, 19, 1, 35, '男', 113.75, '广东省东莞市')
    print(plate.summary())
    print()

    print('大运详情:')
    for du in plate.dayun:
        print(f"  {du['step']}. {du['gz']}  {du['start_age']:.1f}-{du['end_age']:.1f}岁  "
              f"约{du['start_year']}-{du['end_year']}年")

    print()
    print('十二长生:')
    for p in ['year', 'month', 'day', 'hour']:
        dz = plate.sizhu[p]['zhi']
        cs = plate.changsheng[p]
        print(f"  {plate.sizhu[p]['gz']} → {cs}")

    print()
    print('藏干:')
    for p in ['year', 'month', 'day', 'hour']:
        gan_list = plate.canggan[p]
        gan_str = ' '.join(f'{g}({r:.0%})' for g, r in gan_list)
        print(f"  {plate.sizhu[p]['zhi']} → {gan_str}")

    # 关键验证: 起运
    print()
    print('=== 起运验证 ===')
    qy = plate.qiyun
    print(f'出生到节气天数: {qy["diff_days"]} 天')
    print(f'起运年龄: {qy["qiyun_age"]} 岁 (虚岁: {qy["qiyun_age_xu"]})')
    print(f'交运年份: 约{qy["qiyun_year"]:.1f}年')
    print(f'方向: {qy["direction"]}')
    print()
    print(f'预期: 约 3.66岁 (4岁), 2009年交运')
    match = abs(qy["qiyun_age"] - 3.66) < 0.1
    print(f'结果: {"[正确]" if match else "[请检查]"}')
