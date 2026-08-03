#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""密码保护 + 限流"""

import os
import time as _time
from collections import defaultdict

# 密码错误跟踪（IP → 失败时间戳列表）
_pw_failures = defaultdict(list)
PW_MAX_TRIES = 5        # 最多尝试次数
PW_LOCKOUT_MINUTES = 3  # 锁定时长（分钟）

# 加载密码保护配置
WEB_PASSWORD = ""
ADMIN_TOKEN = ""
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_LOCAL = os.path.join(_ROOT, "config.local.py")
if os.path.exists(CONFIG_LOCAL):
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("config_local", CONFIG_LOCAL)
        cfg = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cfg)
        WEB_PASSWORD = getattr(cfg, "WEB_PASSWORD", "")
        ADMIN_TOKEN = getattr(cfg, "ADMIN_TOKEN", "")
    except Exception:
        pass

# 限流存储
_rate_limit_store = defaultdict(list)

# ---- Tier-aware rate limit helpers ----

def check_rate_limit(key: str, max_requests: int = 3, window_minutes: int = 60,
                     user_id: str | None = None) -> bool:
    """简易限流。key 可以是 IP 或 IP:action。
    如果传了 user_id，key 合成为 user:{user_id}:{key}，保证不同 action 独立计数。"""
    actual_key = f"user:{user_id}:{key}" if user_id else key
    import time as _t
    now = _t.time(); window = window_minutes * 60
    _rate_limit_store[actual_key] = [t for t in _rate_limit_store[actual_key] if now - t < window]
    if len(_rate_limit_store[actual_key]) >= max_requests:
        return False
    _rate_limit_store[actual_key].append(now)
    return True


def check_password(ip: str, data: dict) -> str | None:
    """解读访问门槛：已登录（free/pro）直接放行；未登录走访问密码通道。

    产品规则（2026-08-03 King 定）：
    - 已登录用户（free/pro）解读免密，直接放行
    - 未登录用户：持有访问密码可解读；无密码则拒绝并引导注册登录
    - 防爆破锁仅作用于密码通道，登录用户不受影响

    返回 None 表示通过，返回字符串表示错误信息。"""
    # 已登录用户（free/pro）直接放行，不过密码门
    try:
        from flask import request
        from utils.tier import resolve_user_from_request
        user_id, _tier = resolve_user_from_request(request)
        if user_id is not None:
            return None
    except Exception:
        pass  # 登录态解析失败按未登录处理

    # 未登录且未配置访问密码：无通道，引导登录注册
    if not WEB_PASSWORD:
        return "解读需要登录账号，请先登录或注册后使用"

    now = _time.time()
    window = PW_LOCKOUT_MINUTES * 60

    # 清理过期记录 + 检查是否被锁定
    _pw_failures[ip] = [t for t in _pw_failures[ip] if now - t < window]
    if len(_pw_failures[ip]) >= PW_MAX_TRIES:
        remain = round((_pw_failures[ip][0] + window - now) / 60, 1)
        return f"密码错误次数过多，请 {remain} 分钟后再试"

    if data.get("password", "") == WEB_PASSWORD:
        _pw_failures[ip] = []  # 正确则清零
        return None

    # 密码错误：记录
    _pw_failures[ip].append(now)
    remain = PW_MAX_TRIES - len(_pw_failures[ip])
    if remain <= 0:
        return f"密码错误次数过多，请 {PW_LOCKOUT_MINUTES} 分钟后再试"
    return f"密码错误，还剩 {remain} 次机会"

# ============================================================

def check_conv_rate_limit(ip: str, conv_id: str, max_requests: int = 30, window_minutes: int = 60,
                          user_id: str | None = None) -> bool:
    """按对话粒度限流。同一 IP 不同对话互不影响。"""
    return check_rate_limit(f"{ip}:conv:{conv_id}", max_requests, window_minutes, user_id=user_id)


def check_global_ip_limit(ip: str, max_requests: int = 100, window_minutes: int = 60,
                          user_id: str | None = None) -> bool:
    """IP 全局兜底 —— 防止单 IP 无限开对话绕开限流。"""
    return check_rate_limit(f"{ip}:global", max_requests, window_minutes, user_id=user_id)

# ============================================================
