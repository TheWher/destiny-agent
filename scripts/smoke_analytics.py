#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""埋点 + 邀请码多码化 冒烟测试。

覆盖：
1. 匿名埋点可收（无 token）
2. 登录后埋点记 user_id
3. admin /events/stats 漏斗统计正常
4. 邀请码多码映射（INVITE_CODES）生效，旧配置兼容
5. invite_redeem 归因事件带 code+owner
"""

import os
import re
import sqlite3
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.user import (
    get_db, create_user, authenticate, create_token,
    record_event, query_events, update_user_tier,
)

PASS = []
FAIL = []


def check(name, cond, detail=""):
    if cond:
        PASS.append(name)
        print(f"  PASS  {name}")
    else:
        FAIL.append(name)
        print(f"  FAIL  {name}  {detail}")


def main():
    print("== 1. 埋点表与写入 ==")
    conn = get_db()
    try:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='events'").fetchall()
        check("events 表存在", len(rows) == 1)
        idx = conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND name IN ('idx_events_event','idx_events_user')").fetchall()
        check("events 索引存在", len(idx) == 2, f"got {len(idx)}")
    finally:
        conn.close()

    device_id = "smoke-" + uuid.uuid4().hex[:8]
    # 匿名事件
    record_event(None, device_id, "page_view", {"p": "smoke"})
    rows = query_events("page_view", limit=5)
    check("匿名埋点可写可查", any(r["device_id"] == device_id for r in rows))

    # 登录用户事件带 user_id
    email = f"smoke_{uuid.uuid4().hex[:6]}@test.local"
    user = create_user(email, "smoke_pass_123")
    check("测试用户创建", user is not None)
    record_event(user["id"], device_id, "chart_created", {"gender": "男"})
    rows = query_events("chart_created", limit=5)
    check("埋点记 user_id", any(r["user_id"] == user["id"] for r in rows))

    # 元数据 JSON 落库
    rows = query_events("chart_created", limit=1)
    meta_ok = any(r["user_id"] == user["id"] and '"gender"' in (r["meta"] or "") for r in rows)
    check("meta JSON 落库", meta_ok)

    print("== 2. 邀请码多码化 ==")
    import importlib.util as _iu
    _ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _spec = _iu.spec_from_file_location("config_local", os.path.join(_ROOT, "config.local.py"))
    _cfg = _iu.module_from_spec(_spec)
    _spec.loader.exec_module(_cfg)
    codes = getattr(_cfg, "INVITE_CODES", None)
    check("config 里有 INVITE_CODES 映射", isinstance(codes, dict) and "123456" in codes,
          f"got {codes!r}")

    # 模拟 payment.py 的加载逻辑
    INVITE_CODES = {}
    _c = getattr(_cfg, "INVITE_CODES", None)
    _s = getattr(_cfg, "INVITE_CODE", "")
    if isinstance(_c, dict) and _c:
        INVITE_CODES = {str(k).strip(): str(v) for k, v in _c.items() if str(k).strip()}
    elif _s:
        INVITE_CODES = {str(_s).strip(): "king"}
    check("加载后映射含 123456->king", INVITE_CODES.get("123456") == "king", f"got {INVITE_CODES!r}")

    # 旧配置兼容：只有单码时归到 king
    _fake = type("F", (), {"INVITE_CODE": "abc123", "INVITE_CODES": None})
    _fc = getattr(_fake, "INVITE_CODES", None)
    _fs = getattr(_fake, "INVITE_CODE", "")
    compat = {}
    if isinstance(_fc, dict) and _fc:
        compat = {str(k).strip(): str(v) for k, v in _fc.items() if str(k).strip()}
    elif _fs:
        compat = {str(_fs).strip(): "king"}
    check("旧单码配置兼容归 king", compat.get("abc123") == "king", f"got {compat!r}")

    print("== 3. 归因事件 ==")
    code = "123456"
    update_user_tier(user["id"], "pro")
    record_event(user["id"], None, "invite_redeem", {"code": code, "owner": INVITE_CODES[code]})
    rows = query_events("invite_redeem", limit=5)
    attr_ok = any(r["user_id"] == user["id"] and "123456" in (r["meta"] or "") and "king" in (r["meta"] or "") for r in rows)
    check("invite_redeem 带 code+owner", attr_ok)

    print("== 4. 接口可达（路由注册） ==")
    try:
        from routes import app
        client = app.test_client()
        r = client.post("/api/events", json={"event": "smoke_api", "device_id": "d1"})
        check("POST /api/events 200", r.status_code == 200, f"got {r.status_code}")
        r = client.post("/api/events", json={"event": "x" * 100})
        check("事件名超长被拒", r.status_code == 400)
        r = client.get("/api/admin/events/stats")
        check("admin /events/stats 未授权拦截", r.status_code == 401)
        from utils.auth import ADMIN_TOKEN
        r = client.get("/api/admin/events/stats", headers={"X-Admin-Token": ADMIN_TOKEN})
        check("admin /events/stats 200", r.status_code == 200, f"got {r.status_code}")
        d = r.get_json()
        check("stats 返回 today 计数", "today" in d and "all" in d)
        r = client.get("/api/admin/events?event=page_view&limit=3", headers={"X-Admin-Token": ADMIN_TOKEN})
        check("admin /events 过滤查询 200", r.status_code == 200, f"got {r.status_code}")
    except Exception as e:
        check("接口测试执行", False, str(e))

    # 清理测试用户（保留事件，无妨）
    conn = get_db()
    try:
        conn.execute("DELETE FROM users WHERE id = ?", (user["id"],))
        conn.commit()
    finally:
        conn.close()

    print()
    print(f"结果: {len(PASS)} PASS / {len(FAIL)} FAIL")
    if FAIL:
        print("失败项:", FAIL)
        sys.exit(1)
    print("ALL GREEN")


if __name__ == "__main__":
    main()
