#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""会话持久化 + 多轮追问冒烟

会话创建 → 列表 → 重命名 → 追加消息 → 多轮追问 → 删除，
每步验证磁盘文件同步，整条链点到底。

运行：python scripts/smoke_session_chat.py
退出码：0 = PASS，1 = FAIL
"""

import sys
import os
import json
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app import app
from utils.auth import WEB_PASSWORD

SESSIONS_DIR = os.path.join(ROOT, "routes", "sessions")


def main():
    client = app.test_client()
    sid = None
    DEV = f"smoke-dev-{int(time.time())}"
    H = {"X-Device-Id": DEV}
    try:
        # 1) 创建会话 → 磁盘持久化
        r = client.post("/api/ziwei/sessions", headers=H, json={
            "title": "冒烟测试会话",
            "messages": [{"role": "user", "content": "帮我看看命盘"}],
            "plate_data": {"palaces": [], "input": {"birth_datetime": "2005-08-19 01:35", "gender": "男"}},
            "plate_summary": "冒烟盘",
        })
        assert r.status_code == 200, f"创建失败 {r.status_code}: {r.get_data(as_text=True)[:200]}"
        sid = r.get_json()["id"]
        disk = os.path.join(SESSIONS_DIR, f"{sid}.json")
        assert os.path.exists(disk), "会话未写入磁盘"
        print(f"[1/6] 会话创建 OK {sid}，磁盘文件存在")

        # 2) 列表（同一设备才可见：匿名会话按设备指纹隔离）
        r = client.get("/api/ziwei/sessions", headers=H)
        ids = [s["id"] for s in r.get_json()]
        assert sid in ids, "列表不含新会话"
        print(f"[2/6] 会话列表 OK，共 {len(ids)} 个")

        # 3) 重命名 → 磁盘同步
        r = client.put(f"/api/ziwei/sessions/{sid}", headers=H, json={"title": "冒烟改名"})
        assert r.get_json().get("ok"), r.get_data(as_text=True)[:200]
        with open(disk, encoding="utf-8") as f:
            assert json.load(f)["title"] == "冒烟改名", "磁盘 title 未更新"
        print("[3/6] 重命名 OK，磁盘同步")

        # 4) 追加消息 → 磁盘同步
        msgs = [{"role": "user", "content": "追问1"}, {"role": "assistant", "content": "答1"}]
        r = client.patch(f"/api/ziwei/sessions/{sid}", headers=H, json={"messages": msgs})
        assert r.get_json().get("ok"), r.get_data(as_text=True)[:200]
        with open(disk, encoding="utf-8") as f:
            assert len(json.load(f)["messages"]) == 2, "磁盘 messages 未更新"
        print("[4/6] 追加消息 OK，磁盘同步")

        # 5) 多轮追问（真实 LLM 续接）
        r = client.post("/api/ziwei/analyze/continue", json={
            "password": WEB_PASSWORD,
            "messages": [{"role": "user", "content": "帮我看看命盘"}],
            "reply": "我的夫妻宫怎么样？",
        })
        d = r.get_json()
        assert r.status_code == 200 and d.get("success"), f"追问失败: {d}"
        analysis = d.get("analysis", "")
        assert len(analysis) > 30, "追问回复过短"
        print(f"[5/6] 多轮追问 OK，回复 {len(analysis)} 字")

        # 6) 删除 → 磁盘清理
        r = client.delete(f"/api/ziwei/sessions/{sid}", headers=H)
        assert r.get_json().get("ok"), r.get_data(as_text=True)[:200]
        assert not os.path.exists(disk), "磁盘文件未删除"
        print("[6/6] 删除 OK，磁盘文件已清")
        sid = None

        print("\nSMOKE PASS：会话持久化 + 多轮追问全链活着")
        sys.exit(0)
    finally:
        if sid:
            fp = os.path.join(SESSIONS_DIR, f"{sid}.json")
            if os.path.exists(fp):
                os.remove(fp)


if __name__ == "__main__":
    main()
