"""紫微斗数互证贴票脚本 — 引擎参照系票

用法: python scripts/ziwei_ticket.py YYYY M D HH MM 性别(男/女) [经度]
例:   python scripts/ziwei_ticket.py 2005 8 19 1 35 男 113.75

输出固定字段序（频道贴票格式）:
四柱 -> 五行局 -> 命宫/身宫 -> 紫微落宫 -> 十四主星 -> 辅星 -> 生年四化 -> 大限起岁/顺逆

四柱两套: raw(输入时间) + 校正后(页面所见口径, 八字页 apply_solar_correction)
紫微侧不校正(项目设计), 晚子时 index 12 安星按次日。
注意: 宫位功能名取自 iztro-py 原生 palace.translate_name()
（ziwei_paipan 的 PALACE_NAMES_CN[p.index] 固定表有错位 bug, 不可用）
"""
import sys
from datetime import datetime, timedelta

sys.path.insert(0, '.')
from iztro_py import astro
from bazi_calculator import calc_sizhu
from ziwei_calculator import hour_to_shichen_index, FIVE_ELEMENTS_CN

_MINOR_ORDER = ['禄存', '左辅', '右弼', '文昌', '文曲', '天魁', '天钺',
                '擎羊', '陀罗', '火星', '铃星', '地空', '地劫', '天马']


def main(argv):
    year, month, day = int(argv[0]), int(argv[1]), int(argv[2])
    hour, minute = int(argv[3]), int(argv[4])
    gender = argv[5]
    longitude = float(argv[6]) if len(argv) > 6 else 120.0

    sizhu_raw = calc_sizhu(year, month, day, hour, minute)
    dt_cor = datetime(year, month, day, hour, minute) + timedelta(minutes=(longitude - 120.0) * 4.0)
    sizhu_cor = calc_sizhu(dt_cor.year, dt_cor.month, dt_cor.day, dt_cor.hour, dt_cor.minute)
    chart = astro.by_solar(f'{year}-{month}-{day}', hour_to_shichen_index(hour), gender, 'zh-CN')
    soul = chart.get_soul_palace()
    body = chart.get_body_palace()

    print('=== 贴票（引擎参照系）===')
    print('输入: %d-%d-%d %02d:%02d %s / 经度%s / 校正%+.0fmin' % (
        year, month, day, hour, minute, gender, longitude, (longitude - 120.0) * 4.0))

    gz = lambda s: '%s %s %s %s' % (s['year']['gz'], s['month']['gz'], s['day']['gz'], s['hour']['gz'])
    print('四柱 raw: %s' % gz(sizhu_raw))
    print('四柱 校正: %s (页面所见口径)' % gz(sizhu_cor))

    five = FIVE_ELEMENTS_CN.get(str(chart.five_elements_class), str(chart.five_elements_class))
    print('五行局: %s' % five)

    print('命宫: %s%s | 身宫: %s%s' % (soul.heavenly_stem, soul.earthly_branch,
                                     body.heavenly_stem, body.earthly_branch))

    for p in chart.palaces:
        if any(s.name == 'ziweiMaj' for s in p.major_stars):
            print('紫微落宫: %s(%s%s)' % (p.translate_name().replace('宫', ''), p.heavenly_stem, p.earthly_branch))
            break

    print('十四主星:')
    for p in chart.palaces:
        stars = [s.translate_name() for s in p.major_stars]
        if stars:
            print('  %s(%s%s): %s' % (p.translate_name().replace('宫', ''), p.heavenly_stem, p.earthly_branch, ' '.join(stars)))

    print('辅星:')
    for p in chart.palaces:
        stars = [s.translate_name() for s in p.minor_stars if s.translate_name() in _MINOR_ORDER]
        if stars:
            print('  %s(%s%s): %s' % (p.translate_name().replace('宫', ''), p.heavenly_stem, p.earthly_branch, ' '.join(stars)))

    muts = []
    for p in chart.palaces:
        for s in list(p.major_stars) + list(p.minor_stars):
            if s.mutagen:
                muts.append('%s%s@%s' % (s.translate_name(), s.mutagen, p.translate_name().replace('宫', '')))
    print('生年四化: %s' % (' '.join(muts) if muts else '无'))

    yang_year = sizhu_raw['year']['gz'][0] in '甲丙戊庚壬'
    forward = (yang_year and gender == '男') or (not yang_year and gender == '女')
    start_age = soul.decadal.range[0] if soul.decadal else '?'
    print('大限: %s岁起 %s' % (start_age, '顺行' if forward else '逆行'))


if __name__ == '__main__':
    main(sys.argv[1:])
