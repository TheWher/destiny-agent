#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""隐私隔离冒烟：会话跨用户不可见、匿名会话按设备隔离、越权访问 404

背景：线上发现 A 用户能看到 B 用户的排盘（匿名会话对所有人可见 + 单会话接口无鉴权）。
本测试验证修复后的隔离规则。运行：python scripts/smoke_privacy.py
退出码：0 = PASS，1 = FAIL。测试数据结束时清理。
"""

import sys
import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app import app
from models.user import get_db


def _register(client, email, password="test123456"):
    r = client.post("/api/auth/register", json={"email": email, "password": password})
    d = r.get_json()
    assert r.status_code == 201, f"注册失败 {r.status_code}: {d}"
    return d["token"]


def _create_session(client, device, token=None):
    headers = {"X-Device-Id": device}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = client.post("/api/ziwei/sessions",
                    json={"title": "隐私测试", "plate_summary": "sensitive", "messages": []},
                    headers=headers)
    d = r.get_json()
    assert r.status_code == 200, f"建会话失败: {d}"
    return d["id"]


def _list_sessions(client, device, token=None):
    headers = {"X-Device-Id": device}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = client.get("/api/ziwei/sessions", headers=headers)
    return [s["id"] for s in r.get_json()]


def _cleanup(emails):
    conn = get_db()
    try:
        for em in emails:
            row = conn.execute("SELECT id FROM users WHERE email = ?", (em,)).fetchone()
            if row:
                conn.execute("DELETE FROM users WHERE id = ?", (row["id"],))
        conn.commit()
    finally:
        conn.close()


def main():
    stamp = int(time.time())
    emails = [f"priv_a_{stamp}@test.local", f"priv_b_{stamp}@test.local"]
    client = app.test_client()
    try:
        # 准备两个用户 + 两种设备
        tok_a = _register(client, emails[0])
        tok_b = _register(client, emails[1])
        dev_a, dev_b = f"dev-a-{stamp}", f"dev-b-{stamp}"
        dev_anon = f"dev-anon-{stamp}"

        # A 在自己设备建一个会话（未登录，匿名）→ 归 dev_a
        sid_anon = _create_session(client, dev_a)
        # A 登录后再建一个 → 归 user A
        sid_a = _create_session(client, dev_a, tok_a)
        # B 登录建一个 → 归 user B
        sid_b = _create_session(client, dev_b, tok_b)

        # 1. 匿名设备 dev_b 看不到 dev_a 的匿名会话
        lst = _list_sessions(client, dev_b)
        assert sid_anon not in lst, "设备 B 不应看到设备 A 的匿名会话"
        print("[1/7] 匿名会话设备隔离 OK：跨设备不可见")

        # 2. 匿名设备 dev_a 能看到自己的匿名会话（但看不到已绑定的）
        lst = _list_sessions(client, dev_a)
        assert sid_anon in lst, "设备 A 应能看到自己的匿名会话"
        assert sid_a not in lst, "匿名请求不应看到已绑定会话"
        print("[2/7] 匿名会话本设备可见 OK，已绑定会话对匿名不可见")

        # 3. 用户 B 登录看不到 A 的任何会话
        lst = _list_sessions(client, dev_b, tok_b)
        assert sid_a not in lst and sid_anon not in lst, "用户 B 不应看到 A 的会话"
        assert sid_b in lst, "用户 B 应能看到自己的会话"
        print("[3/7] 跨用户列表隔离 OK")

        # 4. 用户 B 直接读 A 的会话 ID → 404
        r = client.get(f"/api/ziwei/sessions/{sid_a}",
                       headers={"Authorization": f"Bearer {tok_b}", "X-Device-Id": dev_b})
        assert r.status_code == 404, f"越权读应 404，实际 {r.status_code}"
        print("[4/7] 越权读取 404 OK")

        # 5. 用户 B 直接改/删 A 的会话 → 404
        r = client.patch(f"/api/ziwei/sessions/{sid_a}", json={"messages": [{"role": "x", "content": "hack"}]},
                         headers={"Authorization": f"Bearer {tok_b}", "X-Device-Id": dev_b})
        assert r.status_code == 404, f"越权改应 404，实际 {r.status_code}"
        r = client.delete(f"/api/ziwei/sessions/{sid_a}",
                          headers={"Authorization": f"Bearer {tok_b}", "X-Device-Id": dev_b})
        assert r.status_code == 404, f"越权删应 404，实际 {r.status_code}"
        assert sid_a in _list_sessions(client, dev_a, tok_a), "A 的会话应未被删除"
        print("[5/7] 越权改/删 404 OK，原会话完好")

        # 6. 归属者正常访问不受影响：A 登录能看到自己的会话
        lst = _list_sessions(client, dev_a, tok_a)
        assert sid_a in lst, "A 应能看到自己的绑定会话"
        r = client.get(f"/api/ziwei/sessions/{sid_a}",
                       headers={"Authorization": f"Bearer {tok_a}", "X-Device-Id": dev_a})
        assert r.status_code == 200, "A 读自己的会话应 200"
        print("[6/7] 归属者访问正常 OK")

        # 7. claimable 不再暴露 orphan 列表
        r = client.get("/api/ziwei/sessions/claimable",
                       headers={"Authorization": f"Bearer {tok_a}", "X-Device-Id": dev_a})
        d = r.get_json()
        assert d.get("orphan_list") == [] and d.get("orphans") == 0, f"orphan 列表不应暴露: {d}"
        print("[7/10] claimable 不暴露无指纹会话 OK")

        # ── 安全分享：独立 share_id 快照，原会话不外传 ──
        # 8. A 分享自己的会话 → 拿到 share_id + url
        r = client.post("/api/ziwei/share", json={"sid": sid_a},
                        headers={"Authorization": f"Bearer {tok_a}", "X-Device-Id": dev_a})
        d = r.get_json()
        assert r.status_code == 200 and d.get("share_id"), f"分享失败: {d}"
        share_id = d["share_id"]
        assert d["url"].startswith("/ziwei/report/share/"), f"分享链接格式错: {d}"
        print("[8/10] 创建分享快照 OK")

        # 9. 公开只读：无鉴权可读快照，且不含用户身份
        r = client.get(f"/api/ziwei/share/{share_id}")
        d = r.get_json()
        assert r.status_code == 200 and d.get("id") == share_id, f"读分享失败: {d}"
        assert "user_id" not in d and "sid" not in d, "分享快照不应含用户身份/原会话 ID"
        assert d.get("plate_data") is not None, "分享快照应含盘面"
        assert d.get("sharer") == emails[0].split("@")[0][:12], f"分享应含署名: {d.get('sharer')}"
        print("[9/10] 分享公开只读 OK，含署名、不含用户身份")

        # 10. 越权：A 不能分享 B 的会话；未登录分享 401；坏 share_id 404
        r = client.post("/api/ziwei/share", json={"sid": sid_b},
                        headers={"Authorization": f"Bearer {tok_a}", "X-Device-Id": dev_a})
        assert r.status_code == 404, f"分享他人会话应 404，实际 {r.status_code}"
        r = client.post("/api/ziwei/share", json={"sid": sid_a})
        assert r.status_code == 401, "未登录分享应 401"
        r = client.get("/api/ziwei/share/no-such-id")
        assert r.status_code == 404, "坏 share_id 应 404"
        print("[10/10] 分享越权/未登录/坏ID 全拦截 OK")

        print("\nSMOKE PASS：会话隐私隔离 + 安全分享全绿")
        sys.exit(0)
    finally:
        _cleanup(emails)


if __name__ == "__main__":
    main()
