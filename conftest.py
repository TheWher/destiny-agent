# -*- coding: utf-8 -*-
"""pytest 根配置（TODO-PAIPAN-PYTEST 参数化，2026-08-06 mose 落）

作用：把项目根目录固定进 sys.path，让所有 test_*.py 与 scripts/ 下的校验尺
都能直接 import app / services / bazi_calculator / ziwei_calculator / scripts.*，
不依赖调用方 cwd。一个入口：pytest 全量 = 全部回归。
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
