#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""密码通道 — 补真测试（挂账销账，2026-08-06 mose 落）

挂账背景：scripts/smoke_password.py（原 test_pw.py 改名，4f18740）是打印式冒烟，
靠人眼读 "All OK"，改名后仍无真断言，且直跑 ModuleNotFoundError（无 sys.path 处理）。
密码逻辑全在 utils/auth.py 的 check_password，纯函数无外部服务，把冒烟流程落成 pytest：

  1. 正确密码 → None（放行）
  2. 错误密码 → 剩余次数递减提示
  3. 连续 5 次错误 → 锁定（防爆破）
  4. 锁定期内正确密码同样被拒
  5. 失败记录清零后正确密码恢复放行
  6. 未配置 WEB_PASSWORD 时无密码通道（产品规则 2026-08-03 King 定）

依赖说明：check_password 内 flask request 解析在 try/except 中，测试无请求上下文
时走 except 分支按未登录处理，恰好落在密码通道上，不依赖任何真实环境。
"""

import pytest

from utils import auth

TEST_IP = "192.168.1.1"  # 与原冒烟脚本一致


@pytest.fixture(autouse=True)
def _clean_failures():
    """每用例独立：清空该 IP 失败记录，防用例间互相污染。"""
    auth._pw_failures[TEST_IP] = []
    yield
    auth._pw_failures[TEST_IP] = []


@pytest.fixture
def _with_password(monkeypatch):
    """密码通道必须配置密码才走锁定逻辑；不依赖 config.local.py 的实值。"""
    monkeypatch.setattr(auth, "WEB_PASSWORD", "test-pass-050819")
    return "test-pass-050819"


def test_correct_password_passes(_with_password):
    assert auth.check_password(TEST_IP, {"password": _with_password}) is None


def test_wrong_password_returns_remaining(_with_password):
    err = auth.check_password(TEST_IP, {"password": "wrong"})
    assert err is not None
    assert "还剩 4 次机会" in err


def test_failures_count_down(_with_password):
    for expect in (4, 3, 2, 1):
        err = auth.check_password(TEST_IP, {"password": "wrong"})
        assert f"还剩 {expect} 次机会" in err


def test_five_wrongs_locks_out(_with_password):
    for _ in range(5):
        err = auth.check_password(TEST_IP, {"password": "wrong"})
    assert "密码错误次数过多" in err
    # 锁定期内正确密码同样被拒（原冒烟脚本第 4 步）
    locked = auth.check_password(TEST_IP, {"password": _with_password})
    assert "密码错误次数过多" in locked


def test_clear_failures_recovers(_with_password):
    for _ in range(5):
        auth.check_password(TEST_IP, {"password": "wrong"})
    auth._pw_failures[TEST_IP] = []  # 等价原冒烟脚本第 5 步
    assert auth.check_password(TEST_IP, {"password": _with_password}) is None


def test_no_password_configured_no_channel(monkeypatch):
    monkeypatch.setattr(auth, "WEB_PASSWORD", "")
    err = auth.check_password(TEST_IP, {"password": "anything"})
    assert err is not None
    assert "登录" in err
