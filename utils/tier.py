#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""付费层级配置 — 集中管理 tier 常量、限流阈值、差异化逻辑。

所有 tier 相关判断必须通过本模块，禁止各路由散落字符串比较。
"""

import re

# ------------------------------------------------------------
# Tier 常量
# ------------------------------------------------------------
TIER_FREE = "free"
TIER_PRO = "pro"
VALID_TIERS = (TIER_FREE, TIER_PRO)

# ------------------------------------------------------------
# 限流配置（每小时上限）
# ------------------------------------------------------------
RATE_LIMITS = {
    TIER_FREE: {
        "ziwei_pan":      5,   # 紫微排盘
        "ziwei_verify":   None,  # 验盘不限
        "ziwei_read":     5,   # 解读
        "bazi_pan":       5,
        "bazi_analysis":  5,
        "bazi_read":      5,
        "conv_message":   30,  # 追问消息
        "global_ip":      100, # IP 全局兜底
    },
    TIER_PRO: {
        "ziwei_pan":      20,
        "ziwei_verify":   None,
        "ziwei_read":     20,
        "bazi_pan":       20,
        "bazi_analysis":  20,
        "bazi_read":      20,
        "conv_message":   100,
        "global_ip":      300,
    },
}

# 窗口（分钟）
RATE_WINDOW_MINUTES = 60


def get_rate_limit(tier: str, action: str) -> int | None:
    """获取某个 tier 某个 action 的每小时上限。None 表示不限。"""
    return RATE_LIMITS.get(tier, RATE_LIMITS[TIER_FREE]).get(action)


def resolve_tier(payload: dict | None) -> str:
    """从 JWT payload 解析 tier，未登录返回 free。"""
    if not payload:
        return TIER_FREE
    tier = payload.get("tier", TIER_FREE)
    return tier if tier in VALID_TIERS else TIER_FREE


def resolve_user_from_request(request) -> tuple[str | None, str]:
    """从 Flask request 解析 JWT，返回 (user_id, tier)。
    tier 以数据库为准（升级/降级即时生效，不依赖 token 刷新），
    JWT payload 仅作身份凭证。未登录返回 (None, 'free')。
    """
    from models.user import verify_token, get_user_by_id
    header = request.headers.get("Authorization", "")
    m = re.match(r"^Bearer\s+(.+)$", header)
    if not m:
        return None, TIER_FREE
    payload = verify_token(m.group(1))
    if not payload:
        return None, TIER_FREE
    user = get_user_by_id(payload["user_id"])
    if not user:
        return payload["user_id"], TIER_FREE
    tier = user.get("tier") or TIER_FREE
    return payload["user_id"], tier if tier in VALID_TIERS else TIER_FREE
