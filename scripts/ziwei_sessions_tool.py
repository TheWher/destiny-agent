#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""紫微斗数会话数据工具 — 发码前数据卫生：列清单 / 补 user_id 归属 / 归档无主会话。

纯标准库（json/csv/os/glob/sys/sqlite3/shutil/argparse），零依赖。
PythonAnywhere 免费档 Bash 控制台直接 `python3 scripts/ziwei_sessions_tool.py ...` 可跑。

用法：
  python3 scripts/ziwei_sessions_tool.py list
  python3 scripts/ziwei_sessions_tool.py claim --email king@example.com --sid abc12345
  python3 scripts/ziwei_sessions_tool.py claim --email king@example.com --all-unowned
  python3 scripts/ziwei_sessions_tool.py archive --all-unowned

幂等语义：只动「无 user_id」的会话，已绑定一律跳过；跑两遍结果一致。
claim 会把 user_id 从数据库校验真实存在（--email 按邮箱查 UUID，--user-id 直查），
防止填一个不存在的 id，补完登录还是看不到。
写/移之前一律打印将改清单并输入 y 确认，否则退出。
"""
import argparse
import csv
import glob
import json
import os
import shutil
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 注意：真实会话目录是 routes/sessions/（routes/ziwei.py 的 _SESSIONS_DIR 相对该模块），
# 项目根 sessions/ 是历史遗留的空目录，指错会静默输出空清单。
DEFAULT_SESSIONS_DIR = os.path.join(ROOT, "routes", "sessions")
DEFAULT_DB = os.path.join(ROOT, "data", "users.db")
DEFAULT_ARCHIVE_DIR = os.path.join(ROOT, "sessions_archive")


def _load_session(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _iter_sessions(sessions_dir):
    for fp in sorted(glob.glob(os.path.join(sessions_dir, "*.json"))):
        try:
            s = _load_session(fp)
        except Exception as e:
            print(f"[警告] 跳过无法解析的会话 {fp}: {e}", file=sys.stderr)
            continue
        sid = os.path.basename(fp)[:-5]
        yield sid, fp, s


def _user_id_from_db(db, email=None, user_id=None):
    if not os.path.exists(db):
        print(f"[错误] 数据库不存在: {db}", file=sys.stderr)
        sys.exit(2)
    conn = sqlite3.connect(db)
    try:
        if email:
            row = conn.execute(
                "SELECT id FROM users WHERE email=?", (email.strip().lower(),)
            ).fetchone()
            if not row:
                print(f"[错误] 邮箱未注册: {email}", file=sys.stderr)
                sys.exit(2)
            return row[0]
        row = conn.execute("SELECT id FROM users WHERE id=?", (user_id,)).fetchone()
        if not row:
            print(f"[错误] user_id 不存在于 users 表: {user_id}", file=sys.stderr)
            sys.exit(2)
        return user_id
    finally:
        conn.close()


def _describe(s):
    return f"{s.get('created_at','')}  {s.get('title','') or ''}  messages={len(s.get('messages',[]) or [])}"


def cmd_list(args):
    w = csv.writer(sys.stdout)
    w.writerow(["sid", "created_at", "title", "user_id", "fingerprint", "messages", "plate_summary"])
    for sid, fp, s in _iter_sessions(args.sessions_dir):
        w.writerow([
            sid,
            s.get("created_at", ""),
            (s.get("title", "") or "").replace("\n", " "),
            s.get("user_id", "") or "",
            s.get("device_fingerprint", "") or "",
            len(s.get("messages", []) or []),
            (s.get("plate_summary", "") or "").replace("\n", " "),
        ])


def cmd_claim(args):
    uid = _user_id_from_db(args.db, email=args.email, user_id=args.user_id)
    targets = []
    for sid, fp, s in _iter_sessions(args.sessions_dir):
        if s.get("user_id"):
            continue  # 已绑定，幂等：跳过
        if not args.all_unowned and sid not in args.sid:
            continue
        targets.append((sid, fp, s))
    if not targets:
        print("没有可绑定的无主会话，退出。")
        return
    print(f"将绑定以下会话到 user_id={uid}：")
    for sid, fp, s in targets:
        print(f"  [{sid}]  {_describe(s)}")
    if not args.yes and input("确认绑定？[y/N] ").strip().lower() != "y":
        print("已取消。")
        sys.exit(1)
    for sid, fp, s in targets:
        s["user_id"] = uid
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(s, f, ensure_ascii=False, indent=2)
        print(f"[已绑定] {sid}")
    print(f"完成，绑定 {len(targets)} 个会话。重启后归属者登录即可见。")


def cmd_archive(args):
    os.makedirs(args.dest_dir, exist_ok=True)
    targets = []
    for sid, fp, s in _iter_sessions(args.sessions_dir):
        if s.get("user_id") and sid not in args.sid:
            continue  # 已绑定：仅显式 --sid 圈定才归档（假绑定/测试账号需人工圈）
        if not args.all_unowned and sid not in args.sid:
            continue
        targets.append((sid, fp, s))
    if not targets:
        print("没有可归档的无主会话，退出。")
        return
    print(f"将归档以下会话到 {args.dest_dir}：")
    for sid, fp, s in targets:
        print(f"  [{sid}]  {_describe(s)}")
    if not args.yes and input("确认归档？[y/N] ").strip().lower() != "y":
        print("已取消。")
        sys.exit(1)
    for sid, fp, s in targets:
        dst = os.path.join(args.dest_dir, os.path.basename(fp))
        shutil.move(fp, dst)
        print(f"[已归档] {sid}")
    print(f"完成，归档 {len(targets)} 个会话。")


def main():
    p = argparse.ArgumentParser(description="紫微会话数据工具")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="列出全部会话（CSV）")
    p_list.add_argument("--sessions-dir", default=DEFAULT_SESSIONS_DIR)
    p_list.set_defaults(fn=cmd_list)

    p_claim = sub.add_parser("claim", help="给无主会话补 user_id 归属")
    p_claim.add_argument("--email", help="King 的注册邮箱（自动查 user_id）")
    p_claim.add_argument("--user-id", help="或直接给 user_id")
    p_claim.add_argument("--sid", nargs="+", default=[], help="要绑定的会话 id，可多个")
    p_claim.add_argument("--all-unowned", action="store_true", help="绑定所有无主会话")
    p_claim.add_argument("--yes", action="store_true", help="跳过确认（谨慎）")
    p_claim.add_argument("--sessions-dir", default=DEFAULT_SESSIONS_DIR)
    p_claim.add_argument("--db", default=DEFAULT_DB)
    p_claim.set_defaults(fn=cmd_claim)

    p_arc = sub.add_parser("archive", help="归档无主会话到归档目录")
    p_arc.add_argument("--sid", nargs="+", default=[], help="要归档的会话 id，可多个")
    p_arc.add_argument("--all-unowned", action="store_true", help="归档所有无主会话")
    p_arc.add_argument("--yes", action="store_true", help="跳过确认（谨慎）")
    p_arc.add_argument("--sessions-dir", default=DEFAULT_SESSIONS_DIR)
    p_arc.add_argument("--dest-dir", default=DEFAULT_ARCHIVE_DIR)
    p_arc.set_defaults(fn=cmd_archive)

    args = p.parse_args()
    if args.cmd == "claim" and not (args.email or args.user_id):
        p.error("claim 需要 --email 或 --user-id")
    if args.cmd in ("claim", "archive") and not (args.sid or args.all_unowned):
        p.error(f"{args.cmd} 需要 --sid 或 --all-unowned")
    args.fn(args)


if __name__ == "__main__":
    main()
