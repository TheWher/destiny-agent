#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Payment routes — 付费升级（新用户福利）+ 邀请码升级

付费路径：POST /api/payment/order 提交付款凭证 → pending → 管理员在
/api/admin/payments 确认后自动开 Pro（当天开通）。
邀请码路径：POST /api/payment/invite 输入邀请码 → 校验通过立即开 Pro。
"""

import base64
import os
import re

from flask import Blueprint, request, jsonify

from models.user import (
    get_user_by_id,
    create_payment_order,
    get_payment_order,
    update_user_tier,
    verify_token,
    record_event,
)

payment_bp = Blueprint("payment", __name__, url_prefix="/api/payment")


# 邀请码：优先读 INVITE_CODES 映射表 {code: owner}，兼容旧 INVITE_CODE 单码（归到 owner="king"）
# 默认关闭
INVITE_CODES = {}
# Pro 定价（元）：付费升级固定金额，前端提示与后端校验共用
PRO_PRICE = 5.0
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
try:
    import importlib.util as _iu
    _spec = _iu.spec_from_file_location("config_local", os.path.join(_ROOT, "config.local.py"))
    _cfg = _iu.module_from_spec(_spec)
    _spec.loader.exec_module(_cfg)
    _codes = getattr(_cfg, "INVITE_CODES", None)
    _single = getattr(_cfg, "INVITE_CODE", "")
    if isinstance(_codes, dict) and _codes:
        INVITE_CODES = {str(k).strip(): str(v) for k, v in _codes.items() if str(k).strip()}
    elif _single:
        # 旧配置兼容：单码归到 owner=king
        INVITE_CODES = {str(_single).strip(): "king"}
    _price = getattr(_cfg, "PRO_PRICE", None)
    if _price:
        try:
            PRO_PRICE = float(_price)
        except (TypeError, ValueError):
            pass
except Exception:
    pass

if not INVITE_CODES:
    print("[payment] WARN: 邀请码为空，邀请码升级功能关闭。检查 config.local.py 是否已上传新版（含 INVITE_CODE 字段）。")


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


_SINGLE_NO_RE = re.compile(r"^[A-Za-z0-9]{6,40}$")
_SCREENSHOT_RE = re.compile(r"^data:image/(jpeg|png);base64,(.+)$", re.S)


def _validate_screenshot(data_url: str) -> tuple:
    """校验转账截图：必须是 JPEG/PNG 的 base64 data URL，解码后 ≤1MB。
    返回 (ok, error_msg)。"""
    if not data_url:
        return False, "请上传转账截图"
    m = _SCREENSHOT_RE.match(data_url)
    if not m:
        return False, "截图格式不对，仅支持 JPEG/PNG"
    try:
        raw = base64.b64decode(m.group(2), validate=True)
    except Exception:
        return False, "截图数据损坏，请重新上传"
    if len(raw) > 1024 * 1024:
        return False, "截图超过 1MB，请压缩后上传"
    return True, ""


@payment_bp.route("/price", methods=["GET"])
def get_price():
    """返回 Pro 定价，前端预填金额用。改价只动 config，前端不写死。"""
    return jsonify({"price": PRO_PRICE, "currency": "CNY"})


@payment_bp.route("/order", methods=["POST"])
def create_order():
    """付费升级：提交付款凭证（转账单号 + 金额 + 昵称 + 截图），校验通过即自动开通 Pro。
    格式是闸门：单号松正则、金额必须等于定价、截图必传。"""
    payload = _require_auth()
    user, err = _pro_or_404(payload)
    if err:
        return err

    data = request.get_json(silent=True) or {}
    single_no = (data.get("single_no") or "").strip()
    amount = data.get("amount")
    nickname = (data.get("nickname") or "").strip()
    screenshot = (data.get("screenshot") or "").strip()

    # 1. 单号：松正则，先宽松后收紧，样本来自第一批真实用户
    if not _SINGLE_NO_RE.match(single_no):
        return jsonify({"error": "转账单号格式不对：6-40 位字母或数字，不含空格"}), 400
    # 2. 金额：必须等于定价（业务一致性校验）
    try:
        amount_f = float(amount)
    except (TypeError, ValueError):
        return jsonify({"error": "请填写转账金额"}), 400
    if abs(amount_f - PRO_PRICE) > 0.001:
        return jsonify({"error": f"金额应为 {PRO_PRICE:g} 元，请核对转账金额"}), 400
    # 3. 昵称：可空，仅限长度
    if len(nickname) > 30:
        return jsonify({"error": "昵称过长，请精简到 30 字以内"}), 400
    # 4. 截图：唯一防蓄意白嫖的层，必传
    img_ok, img_err = _validate_screenshot(screenshot)
    if not img_ok:
        return jsonify({"error": img_err}), 400

    # 校验全过：自动开通 Pro + 订单留痕（confirmed）
    update_user_tier(user["id"], "pro")
    order = create_payment_order(
        user["id"], user["email"], "pay",
        f"单号:{single_no}" + (f" 昵称:{nickname}" if nickname else ""),
        amount=amount_f, screenshot=screenshot, auto_confirm=True,
    )
    record_event(user["id"], None, "upgrade_order_created", {"method": "pay_auto", "amount": amount_f})
    return jsonify({"success": True, "order": order, "tier": "pro"})


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
    if not INVITE_CODES:
        return jsonify({"error": "邀请码功能暂未开放"}), 400
    if not code:
        return jsonify({"error": "请填写邀请码"}), 400
    if code not in INVITE_CODES:
        return jsonify({"error": "邀请码无效"}), 400

    update_user_tier(user["id"], "pro")
    order = create_payment_order(user["id"], user["email"], "invite", f"邀请码:{code}")
    # 归因：记一条 invite_redeem 事件，meta 带码和发放人，复盘能对到人
    record_event(user["id"], None, "invite_redeem", {"code": code, "owner": INVITE_CODES[code]})
    return jsonify({"success": True, "order": order})
