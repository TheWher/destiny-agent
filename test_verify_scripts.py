# -*- coding: utf-8 -*-
"""校验尺 pytest 统一入口（TODO-PAIPAN-PYTEST，2026-08-06 mose 落）

把 scripts/ 下不带 test_ 前缀、pytest 不自动收集的校验尺脚本挂进 pytest 常驻回归：
- verify_laiyin_anchors.py：来因宫双锚校验尺（旗舰，约 80+ 断言）
- verify_geju_mingzhu.py：日月系格局 6 盘 × 19 断言（与 test_ziwei 日月并明组共享同一数据源，
  盘与期望只定义于此，双维护已消除）

手动轨 python scripts/verify_*.py 行为不变（exit 0/1 + 计数打印），
本文件只做 pytest 轨挂载，不动脚本逻辑。
"""
from scripts.verify_laiyin_anchors import run as laiyin_run
from scripts.verify_geju_mingzhu import run as geju_run
from scripts.verify_fixture_snap import run as fixture_run


def test_laiyin_anchors_regression():
    """来因宫双锚校验尺全断言常驻回归"""
    failures = laiyin_run()
    assert not failures, f"laiyin 校验尺 {len(failures)} 项断言未过: {failures}"


def test_geju_mingzhu_regression():
    """日月系格局 6 盘 × 19 断言常驻回归"""
    failures = geju_run()
    assert not failures, f"geju 校验尺 {len(failures)} 项断言未过: {failures}"


def test_fixture_snap_regression():
    """解析器三层回归骨架（fixture 值集快照锁版本，snap-20260812-0）"""
    failures = fixture_run()
    assert not failures, f"fixture 校验 {len(failures)} 项断言未过: {failures}"


def test_verify_geju_canon_no_false_positive():
    """LLM-verify 格局 canon 回归（2026-08-14 mose 修，生产 bug）：King 盘日月并明成立，
    提及「日月并明」不得被误报为盘面无此格局、不得被修正循环改写为「无日月并明」。"""
    import ziwei_calculator as z
    from services.ziwei_analysis import verify_interpretation_against_plate, apply_correction_loop

    plate = z.ziwei_paipan(2005, 8, 19, 1, 35, '男')
    text = '此盘日月并明成立，明珠出海亦成，财官双美之局。'
    v = verify_interpretation_against_plate(text, plate)
    geju_issues = [i for i in v['issues'] if i['type'] == 'geju']
    assert not geju_issues, f'日月并明正确提及被误报: {geju_issues}'
    assert 'geju' not in v['unverified'], f'格局校验被静默跳过: {v["unverified"]}'
    c = apply_correction_loop(text, plate, max_rounds=2)
    assert c['fixed'] == [], f'修正循环误改写: {c["fixed"]}'
    assert '无日月并明' not in c['text'], f'文本被错误改写: {c["text"]}'
