#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Auth routes — register, login, me, logout, admin tier management."""

from flask import Blueprint, request, jsonify

from models.user import create_user, authenticate, get_user_by_id, create_token, verify_token, get_db
from utils.tier import VALID_TIERS
from utils.auth import ADMIN_TOKEN, check_rate_limit
from utils.email_check import check_email_quality

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

_EMAIL_RE = r"(?i)^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$"

# 弱密码黑名单（硬拦截：密码强度是用户可控的，不误伤）
_WEAK_PASSWORDS = {
    "123456", "1234567", "12345678", "123456789", "1234567890", "password",
    "password1", "passw0rd", "qwerty", "abc123", "111111", "000000",
    "654321", "666666", "888888", "999999", "123123", "123321",
    "iloveyou", "admin", "welcome", "monkey", "dragon", "master",
    "letmein", "football", "princess", "sunshine", "login", "test123",
}

# 注册 IP 限流：每小时每 IP 最多 10 次注册
_REGISTER_RATE_MAX = 10
_REGISTER_RATE_WINDOW = 60


def _require_auth():
    """Extract and verify JWT from Authorization header. Returns payload or None."""
    import re as _re
    header = request.headers.get("Authorization", "")
    m = _re.match(r"^Bearer\s+(.+)$", header)
    if not m:
        return None
    return verify_token(m.group(1))


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip()
    password = (data.get("password") or "").strip()

    if not email or not password:
        return jsonify({"error": "邮箱和密码不能为空"}), 400
    import re
    if not re.match(_EMAIL_RE, email):
        return jsonify({"error": "邮箱格式不正确"}), 400

    # 注册 IP 限流（防批量注册）
    ip = request.remote_addr or "unknown"
    if not check_rate_limit(f"{ip}:register", max_requests=_REGISTER_RATE_MAX,
                            window_minutes=_REGISTER_RATE_WINDOW):
        return jsonify({"error": "注册太频繁，请稍后再试"}), 429

    # 密码规范：8 位以上 + 弱密码黑名单
    if len(password) < 8:
        return jsonify({"error": "密码至少 8 位"}), 400
    if password.lower() in _WEAK_PASSWORDS:
        return jsonify({"error": "密码太简单，换一个复杂点的"}), 400

    # 邮箱质量软提示（不拦截，只提示）
    quality = check_email_quality(email)

    user = create_user(email, password)
    if not user:
        return jsonify({"error": "该邮箱已注册"}), 409

    token = create_token(user)
    resp = {
        "success": True,
        "token": token,
        "user": {"id": user["id"], "email": user["email"], "tier": user["tier"]},
    }
    if quality.get("warning"):
        resp["warning"] = quality["warning"]
    return jsonify(resp), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip()
    password = (data.get("password") or "").strip()

    if not email or not password:
        return jsonify({"error": "邮箱和密码不能为空"}), 400

    user = authenticate(email, password)
    if not user:
        return jsonify({"error": "邮箱或密码错误"}), 401

    token = create_token(user)
    return jsonify({
        "success": True,
        "token": token,
        "user": {"id": user["id"], "email": user["email"], "tier": user["tier"]},
    })


@auth_bp.route("/me", methods=["GET"])
def me():
    payload = _require_auth()
    if not payload:
        return jsonify({"error": "未登录或 token 已过期"}), 401
    user = get_user_by_id(payload["user_id"])
    if not user:
        return jsonify({"error": "用户不存在"}), 404
    return jsonify({
        "user": {"id": user["id"], "email": user["email"], "tier": user["tier"],
                 "created_at": user["created_at"], "last_login": user["last_login"]},
    })


# ------------------------------------------------------------
# Admin tier management
# ------------------------------------------------------------
admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


def _check_admin():
    """Verify admin token from Authorization header or X-Admin-Token header."""
    if not ADMIN_TOKEN:
        return False
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        token = header[7:]
    else:
        token = request.headers.get("X-Admin-Token", "")
    return token == ADMIN_TOKEN


@admin_bp.route("/users/<user_id>/tier", methods=["PATCH"])
def set_tier(user_id):
    if not _check_admin():
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    tier = (data.get("tier") or "").strip().lower()
    if tier not in VALID_TIERS:
        return jsonify({"error": f"无效的 tier，可选: {VALID_TIERS}"}), 400

    conn = get_db()
    try:
        cur = conn.execute("UPDATE users SET tier = ? WHERE id = ?", (tier, user_id))
        conn.commit()
        if cur.rowcount == 0:
            return jsonify({"error": "用户不存在"}), 404
        return jsonify({"success": True, "user_id": user_id, "tier": tier})
    finally:
        conn.close()


@admin_bp.route("/users", methods=["GET"])
def list_users():
    if not _check_admin():
        return jsonify({"error": "unauthorized"}), 401

    tier_filter = request.args.get("tier")
    conn = get_db()
    try:
        if tier_filter and tier_filter in VALID_TIERS:
            rows = conn.execute(
                "SELECT id, email, tier, created_at, last_login FROM users WHERE tier = ? ORDER BY created_at DESC",
                (tier_filter,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, email, tier, created_at, last_login FROM users ORDER BY created_at DESC",
            ).fetchall()
        return jsonify({
            "users": [dict(r) for r in rows],
            "count": len(rows),
        })
    finally:
        conn.close()


# ------------------------------------------------------------
# Admin payment orders
# ------------------------------------------------------------
@admin_bp.route("/payments", methods=["GET"])
def list_payments():
    """订单列表，?status=pending 只看待确认。"""
    if not _check_admin():
        return jsonify({"error": "unauthorized"}), 401
    from models.user import list_payment_orders
    status = request.args.get("status")
    orders = list_payment_orders(status)
    return jsonify({"orders": orders, "count": len(orders)})


@admin_bp.route("/payments/<order_id>/confirm", methods=["POST"])
def confirm_payment(order_id):
    """确认付费订单：升级用户 Pro + 标记 confirmed。"""
    if not _check_admin():
        return jsonify({"error": "unauthorized"}), 401
    from models.user import confirm_payment_order
    order = confirm_payment_order(order_id)
    if not order:
        return jsonify({"error": "订单不存在"}), 404
    return jsonify({"order": order})


@admin_bp.route("/payments/<order_id>/reject", methods=["POST"])
def reject_payment(order_id):
    """驳回订单：标记 rejected，不改 tier。"""
    if not _check_admin():
        return jsonify({"error": "unauthorized"}), 401
    from models.user import reject_payment_order
    order = reject_payment_order(order_id)
    if not order:
        return jsonify({"error": "订单不存在"}), 404
    return jsonify({"order": order})
