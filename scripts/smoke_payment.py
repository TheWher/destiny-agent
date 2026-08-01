#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""支付模块冒烟：付费升级（提交凭证→pending→admin确认→Pro）+ 邀请码升级

运行：python scripts/smoke_payment.py
退出码：0 = PASS，1 = FAIL。测试用户/订单会在结束时清理。
"""

import sys
import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app import app
from utils.auth import ADMIN_TOKEN
from models.user import get_db


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
        # ── 邀请码路径 ──
        tok_a = _register(client, emails[0])
        r = client.post("/api/payment/invite", json={"code": "123456"},
                        headers={"Authorization": f"Bearer {tok_a}"})
        d = r.get_json()
        assert r.status_code == 200 and d.get("success"), f"邀请码升级失败: {d}"
        assert d["order"]["status"] == "confirmed", "邀请码订单应为 confirmed"
        assert _me(client, tok_a)["tier"] == "pro", "邀请码升级后 tier 应为 pro"
        print("[1/5] 邀请码升级 OK：直接开 Pro，订单 confirmed")

        # 错误邀请码
        r = client.post("/api/payment/invite", json={"code": "000000"},
                        headers={"Authorization": f"Bearer {tok_a}"})
        assert r.status_code == 400, "错误邀请码应被拒"
        print("[2/5] 无效邀请码拦截 OK")

        # ── 付费路径 ──
        tok_b = _register(client, emails[1])
        r = client.post("/api/payment/order", json={"credential": "微信单号1234567890 昵称阿豪"},
                        headers={"Authorization": f"Bearer {tok_b}"})
        d = r.get_json()
        assert r.status_code == 200 and d.get("success"), f"提交凭证失败: {d}"
        oid = d["order"]["id"]
        assert d["order"]["status"] == "pending", "付费订单应为 pending"
        assert _me(client, tok_b)["tier"] == "free", "确认前 tier 应保持 free"
        print(f"[3/5] 付费凭证提交 OK：订单 {oid} pending，tier 未变")

        # 未登录提交应 401
        r = client.post("/api/payment/order", json={"credential": "x"})
        assert r.status_code == 401, "未登录应 401"
        print("[4/5] 未登录拦截 OK")

        # admin 确认 → Pro
        r = client.post(f"/api/admin/payments/{oid}/confirm",
                        headers={"X-Admin-Token": ADMIN_TOKEN})
        d = r.get_json()
        assert r.status_code == 200 and d["order"]["status"] == "confirmed", f"admin 确认失败: {d}"
        assert _me(client, tok_b)["tier"] == "pro", "确认后 tier 应为 pro"
        print("[5/5] admin 确认 OK：订单 confirmed，用户开 Pro")

        print("\nSMOKE PASS：付费升级 + 邀请码升级全链活着")
        sys.exit(0)
    finally:
        _cleanup(emails)


if __name__ == "__main__":
    main()
