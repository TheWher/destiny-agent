#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Payment routes — 付费升级（新用户福利）+ 邀请码升级

付费路径：POST /api/payment/order 提交付款凭证 → pending → 管理员在
/api/admin/payments 确认后自动开 Pro（当天开通）。
邀请码路径：POST /api/payment/invite 输入邀请码 → 校验通过立即开 Pro。
"""

import os

from flask import Blueprint, request, jsonify

from models.user import (
    get_user_by_id,
    create_payment_order,
    get_payment_order,
    update_user_tier,
    verify_token,
)

payment_bp = Blueprint("payment", __name__, url_prefix="/api/payment")


# 邀请码：从 config.local.py 读取（默认关闭）
INVITE_CODE = ""
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
try:
    import importlib.util as _iu
    _spec = _iu.spec_from_file_location("config_local", os.path.join(_ROOT, "config.local.py"))
    _cfg = _iu.module_from_spec(_spec)
    _spec.loader.exec_module(_cfg)
    INVITE_CODE = getattr(_cfg, "INVITE_CODE", "")
except Exception:
    pass

if not INVITE_CODE:
    print("[payment] WARN: INVITE_CODE 为空，邀请码升级功能关闭。检查 config.local.py 是否已上传新版（含 INVITE_CODE 字段）。")


def _require_auth():
    """Extract and verify JWT from Authorization header. Returns payload or None."""
    import re as _re
    header = request.headers.get("Authorization", "")
    m = _re.match(r"^Bearer\s+(.+)$", header)
    if not m:
        return None
    return verify_token(m.group(1))


def _pro_or_404(payload):
    """返回 (user, error_response)。未登录/不存在/已是 Pro 时返回错误响应。"""
    user = get_user_by_id(payload["user_id"]) if payload else None
    if not user:
        return None, (jsonify({"error": "未登录或 token 已过期"}), 401)
    if user["tier"] == "pro":
        return None, (jsonify({"error": "你已经是 Pro 用户了"}), 400)
    return user, None


@payment_bp.route("/order", methods=["POST"])
def create_order():
    """付费升级：提交付款凭证（微信转账单号 + 昵称）"""
    payload = _require_auth()
    user, err = _pro_or_404(payload)
    if err:
        return err

    data = request.get_json(silent=True) or {}
    credential = (data.get("credential") or "").strip()
    if not credential:
        return jsonify({"error": "请填写付款凭证（转账单号+昵称）"}), 400
    if len(credential) > 200:
        return jsonify({"error": "凭证过长，请精简到 200 字以内"}), 400

    order = create_payment_order(user["id"], user["email"], "pay", credential)
    return jsonify({"success": True, "order": order})


@payment_bp.route("/order/<order_id>", methods=["GET"])
def get_order(order_id):
    """查询订单状态（仅本人）"""
    payload = _require_auth()
    if not payload:
        return jsonify({"error": "未登录或 token 已过期"}), 401
    order = get_payment_order(order_id)
    if not order or order["user_id"] != payload["user_id"]:
        return jsonify({"error": "订单不存在"}), 404
    return jsonify({"order": order})


@payment_bp.route("/invite", methods=["POST"])
def redeem_invite():
    """邀请码升级：输入邀请码直接开通 Pro"""
    payload = _require_auth()
    user, err = _pro_or_404(payload)
    if err:
        return err

    data = request.get_json(silent=True) or {}
    code = (data.get("code") or "").strip()
    if not INVITE_CODE:
        return jsonify({"error": "邀请码功能暂未开放"}), 400
    if not code:
        return jsonify({"error": "请填写邀请码"}), 400
    if code != INVITE_CODE:
        return jsonify({"error": "邀请码无效"}), 400

    update_user_tier(user["id"], "pro")
    order = create_payment_order(user["id"], user["email"], "invite", "邀请码:" + code)
    return jsonify({"success": True, "order": order})
