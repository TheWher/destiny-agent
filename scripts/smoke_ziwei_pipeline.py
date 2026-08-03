# -*- coding: utf-8 -*-
"""紫微解读链路端到端 smoke（2026-08-04 加）

覆盖: 排盘 -> plate_to_dict -> user_message 注入(古籍三层) -> 校验器(正确/错误文本)
断言失败退出码 1, 部署前可跑。

用法: python scripts/smoke_ziwei_pipeline.py
"""
import sys

sys.path.insert(0, '.')
from ziwei_calculator import ziwei_paipan, plate_to_dict
from services.ziwei_analysis import _build_ziwei_user_message, verify_interpretation_against_plate

FAIL = []


def check(name, cond, detail=''):
    print(('PASS' if cond else 'FAIL'), name, detail)
    if not cond:
        FAIL.append(name)


def main():
    # 1. 排盘（晚子时单，锚点集最全）
    pl = ziwei_paipan(2005, 8, 19, 23, 10, '男')
    plate = plate_to_dict(pl, {'birth_datetime': '2005-08-19 23:10', 'gender': '男'})
    check('排盘 12 宫', len(plate.get('palaces', [])) == 12)
    check('五行局水二', plate.get('five_elements_class') == '水二局')

    # 2. 注入（古籍三层 + 口径）
    msg = _build_ziwei_user_message(plate, None)
    check('注入含诸星问答论', '诸星问答论' in msg)
    check('注入含赋文总纲', '卷一赋文总纲' in msg)
    check('注入含格局诗', '格局诗' in msg)
    check('注入含口径声明', '引擎' in msg and '禁止' in msg)
    check('注入长度合理', 8000 < len(msg) < 20000, f'len={len(msg)}')

    # 3. 校验器：正确文本 0 误报
    good = '命宫甲申坐长生，紫微在父母宫，天机化禄在命宫，大限2岁起逆行。'
    vg = verify_interpretation_against_plate(good, plate)
    check('正确文本 0 误报', len(vg['issues']) == 0, str(vg['issues']))
    check('正确文本 unverified 空', vg['unverified'] == [], str(vg['unverified']))

    # 4. 校验器：错误文本全逮（星宫/长生/大限顺逆/大限起岁）
    bad = '紫微坐命，迁移宫坐长生，大限3岁起顺行。'
    vb = verify_interpretation_against_plate(bad, plate)
    types = sorted({i['type'] for i in vb['issues']})
    check('错误文本四类全逮', set(types) >= {'star_palace', 'changsheng', 'decadal_dir', 'decadal_start'}, str(types))
    check('错误文本带 raw 原文', all(i.get('raw') for i in vb['issues']))

    # 5. 校验器：别名（帝座/仆役）命中
    alias = '帝座在命宫，仆役宫坐长生。'
    va = verify_interpretation_against_plate(alias, plate)
    check('别名归一化命中', len(va['issues']) >= 2, str(va['issues']))

    # 6. 裸盘调用 delivery gate
    plate_no_input = plate_to_dict(pl, {})
    vn = verify_interpretation_against_plate('大限2岁起逆行。', plate_no_input)
    check('缺 input 标 unverified', 'decadal_dir' in vn['unverified'], str(vn['unverified']))

    print()
    if FAIL:
        print('FAIL:', len(FAIL), '项 ->', FAIL)
        sys.exit(1)
    print('端到端 smoke 全部通过（排盘/注入/校验/别名/gate）')


if __name__ == '__main__':
    main()
