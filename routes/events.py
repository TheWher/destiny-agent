#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Analytics events — 最小埋点：前端打点，服务端落 SQLite。

POST /api/events  body: {event, meta?, device_id?}
- event: 事件名（<=64 字符）
- meta:  可选的 JSON 对象（时长、来源等）
- device_id: 匿名设备指纹（未登录用户归因用）
鉴权可选：带有效 token 自动记 user_id，不带则记匿名。
失败静默：埋点不能影响主流程。
"""

from flask import Blueprint, jsonify, request

from models.user import record_event, verify_token

events_bp = Blueprint("events", __name__, url_prefix="/api/events")


@events_bp.route("", methods=["POST"])
def track():
    data = request.get_json(silent=True) or {}
    event = (data.get("event") or "").strip()
    if not event or len(event) > 64:
        return jsonify({"error": "bad event"}), 400
    meta = data.get("meta")
    if meta is not None and not isinstance(meta, dict):
        return jsonify({"error": "meta must be an object"}), 400

    # 有 token 记 user_id，没有记匿名
    user_id = None
    import re as _re
    header = request.headers.get("Authorization", "")
    m = _re.match(r"^Bearer\s+(.+)$", header)
    if m:
        payload = verify_token(m.group(1))
        if payload:
            user_id = payload["user_id"]

    device_id = (data.get("device_id") or "").strip()
    if len(device_id) > 64:
        device_id = device_id[:64]

    record_event(user_id, device_id or None, event, meta if isinstance(meta, dict) else None)
    return jsonify({"success": True})
