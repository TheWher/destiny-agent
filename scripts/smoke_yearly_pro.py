#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Pro 专属「大限流年深度解读」冒烟 — tier 实时化回归

覆盖三条验收线：
  1. free 用户调用 → 403 pro_required（被挡）
  2. 邀请码升级后（不重新登录，旧 token）→ 立即放行（tier 实时读生效）
  3. Pro 全链路 LLM 解读 → 返回分析文本

运行：python scripts/smoke_yearly_pro.py
退出码：0 = PASS，1 = FAIL。测试用户/订单自动清理。
"""

import sys
import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app import app
from utils.auth import WEB_PASSWORD
from models.user import get_db


def main():
    stamp = int(time.time())
    email = f"smoke_yearly_{stamp}@test.local"
    client = app.test_client()
    try:
        r = client.post("/api/auth/register", json={"email": email, "password": "strongpass88"})
        assert r.status_code == 201, f"注册失败: {r.get_json()}"
        tok = r.get_json()["token"]
        h = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}

        payload = {"year": 2005, "month": 8, "day": 19, "hour": 1,
                   "gender": "男", "target_year": 2026, "is_lunar": False,
                   "password": WEB_PASSWORD}

        # 1) free 被挡
        r = client.post("/api/ziwei/analyze/yearly", json=payload, headers=h)
        d = r.get_json()
        assert r.status_code == 403 and d.get("pro_required"), f"[1] free 应 403: {r.status_code} {d}"
        print("[1/3] free 拦截 OK：403 pro_required")

        # 2) 邀请码升级（旧 token 不刷新）→ tier 实时读立即生效
        r = client.post("/api/payment/invite", json={"code": "123456"}, headers=h)
        assert r.status_code == 200, f"[2] 邀请码升级失败: {r.get_json()}"
        print("[2/3] 邀请码升级 OK（token 未变，tier 已实时读）")

        # 3) Pro 全链路
        r = client.post("/api/ziwei/analyze/yearly", json=payload, headers=h)
        d = r.get_json()
        assert r.status_code == 200 and d.get("success"), f"[3] Pro 调用失败: {r.status_code} {d}"
        assert len(d["analysis"]) > 100, "[3] 分析文本过短"
        print(f"[3/3] Pro 全链路 OK，输出 {len(d['analysis'])} 字")

        print("\nSMOKE PASS：free 被挡 / 升级即时生效 / Pro 放行，三条验收线全过")
        sys.exit(0)
    except AssertionError as e:
        print("FAIL:", e)
        sys.exit(1)
    finally:
        conn = get_db()
        try:
            row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            if row:
                conn.execute("DELETE FROM payment_orders WHERE user_id = ?", (row["id"],))
                conn.execute("DELETE FROM users WHERE id = ?", (row["id"],))
            conn.commit()
        finally:
            conn.close()


if __name__ == "__main__":
    main()
