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


def test_laiyin_anchors_regression():
    """来因宫双锚校验尺全断言常驻回归"""
    failures = laiyin_run()
    assert not failures, f"laiyin 校验尺 {len(failures)} 项断言未过: {failures}"


def test_geju_mingzhu_regression():
    """日月系格局 6 盘 × 19 断言常驻回归"""
    failures = geju_run()
    assert not failures, f"geju 校验尺 {len(failures)} 项断言未过: {failures}"
