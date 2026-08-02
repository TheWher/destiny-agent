#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""支付模块冒烟：付费自动开通（校验通过即开 Pro）+ 邀请码升级 + admin 撤销

运行：python scripts/smoke_payment.py
退出码：0 = PASS，1 = FAIL。测试用户/订单会在结束时清理。
"""

import base64
import sys
import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app import app
from utils.auth import ADMIN_TOKEN
from models.user import get_db


# 1x1 像素 JPEG（最小合法图）
_JPEG_B64 = (
    "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAABAAAAAAAAAAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AVN//2Q=="
)
_SCREENSHOT = f"data:image/jpeg;base64,{_JPEG_B64}"


def _register(client, email, password="test123456"):
    r = client.post("/api/auth/register", json={"email": email, "password": password})
    d = r.get_json()
    assert r.status_code == 201, f"注册失败 {r.status_code}: {d}"
    return d["token"]


def _me(client, token):
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    return r.get_json()["user"]


def _cleanup(emails):
    conn = get_db()
    try:
        for em in emails:
            row = conn.execute("SELECT id FROM users WHERE email = ?", (em,)).fetchone()
            if row:
                conn.execute("DELETE FROM payment_orders WHERE user_id = ?", (row["id"],))
                conn.execute("DELETE FROM users WHERE id = ?", (row["id"],))
        conn.commit()
    finally:
        conn.close()


def main():
    stamp = int(time.time())
    emails = [f"smoke_pay_{stamp}@test.local", f"smoke_invite_{stamp}@test.local"]
    client = app.test_client()
    try:
        # ── 邀请码路径（不变） ──
        tok_a = _register(client, emails[0])
        r = client.post("/api/payment/invite", json={"code": "123456"},
                        headers={"Authorization": f"Bearer {tok_a}"})
        d = r.get_json()
        assert r.status_code == 200 and d.get("success"), f"邀请码升级失败: {d}"
        assert d["order"]["status"] == "confirmed", "邀请码订单应为 confirmed"
        assert _me(client, tok_a)["tier"] == "pro", "邀请码升级后 tier 应为 pro"
        print("[1/8] 邀请码升级 OK：直接开 Pro，订单 confirmed")

        r = client.post("/api/payment/invite", json={"code": "000000"},
                        headers={"Authorization": f"Bearer {tok_a}"})
        assert r.status_code == 400, "错误邀请码应被拒"
        print("[2/8] 无效邀请码拦截 OK")

        # ── 付费自动开通路径 ──
        tok_b = _register(client, emails[1])
        r = client.post("/api/payment/order",
                        json={"single_no": "ABC1234567", "amount": 5,
                              "nickname": "阿豪", "screenshot": _SCREENSHOT},
                        headers={"Authorization": f"Bearer {tok_b}"})
        d = r.get_json()
        assert r.status_code == 200 and d.get("success"), f"自动开通失败: {d}"
        oid = d["order"]["id"]
        assert d["order"]["status"] == "confirmed", "自动开通订单应为 confirmed"
        assert d["order"]["amount"] == "5.0" or str(d["order"]["amount"]) in ("5", "5.0"), \
            f"订单应记录金额: {d['order'].get('amount')}"
        assert _me(client, tok_b)["tier"] == "pro", "提交即开，tier 应为 pro"
        print("[3/8] 付费自动开通 OK：校验通过立即 Pro，订单 confirmed 留痕")

        # 金额不对 → 拒
        r = client.post("/api/payment/order",
                        json={"single_no": "ABC1234567", "amount": 10, "screenshot": _SCREENSHOT},
                        headers={"Authorization": f"Bearer {tok_b}"})
        assert r.status_code == 400, "金额不等于定价应被拒"
        print("[4/8] 金额校验 OK：不等于定价拒绝")

        # 缺截图 → 拒
        r = client.post("/api/payment/order",
                        json={"single_no": "ABC1234567", "amount": 5},
                        headers={"Authorization": f"Bearer {tok_b}"})
        assert r.status_code == 400, "缺截图应被拒"
        print("[5/8] 截图必传 OK")

        # 单号格式错 → 拒
        r = client.post("/api/payment/order",
                        json={"single_no": "单号!@#", "amount": 5, "screenshot": _SCREENSHOT},
                        headers={"Authorization": f"Bearer {tok_b}"})
        assert r.status_code == 400, "单号格式错应被拒"
        print("[6/8] 单号格式校验 OK：乱填进不来")

        # 未登录 → 401
        r = client.post("/api/payment/order", json={"single_no": "ABC1234567", "amount": 5,
                                                    "screenshot": _SCREENSHOT})
        assert r.status_code == 401, "未登录应 401"
        print("[7/8] 未登录拦截 OK")

        # admin 撤销 → 用户回 free + 订单 revoked
        r = client.post(f"/api/admin/payments/{oid}/revoke",
                        headers={"X-Admin-Token": ADMIN_TOKEN})
        d = r.get_json()
        assert r.status_code == 200 and d["order"]["status"] == "revoked", f"撤销失败: {d}"
        assert _me(client, tok_b)["tier"] == "free", "撤销后 tier 应回 free"
        print("[8/8] admin 撤销 OK：用户降回 free，订单 revoked")

        print("\nSMOKE PASS：自动开通 + 格式闸门 + 撤销全链活着")
        sys.exit(0)
    finally:
        _cleanup(emails)


if __name__ == "__main__":
    main()
