#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Auth routes — register, login, me, logout."""

from flask import Blueprint, request, jsonify

from models.user import create_user, authenticate, get_user_by_id, create_token, verify_token

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

_EMAIL_RE = r"(?i)^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$"


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
    if len(password) < 6:
        return jsonify({"error": "密码至少6位"}), 400

    user = create_user(email, password)
    if not user:
        return jsonify({"error": "该邮箱已注册"}), 409

    token = create_token(user)
    return jsonify({
        "success": True,
        "token": token,
        "user": {"id": user["id"], "email": user["email"], "tier": user["tier"]},
    }), 201


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
