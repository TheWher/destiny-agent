#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Auth models — SQLite user store, password hashing, JWT tokens."""

import hashlib
import hmac
import json
import os
import sqlite3
import time
import uuid
from base64 import urlsafe_b64encode, urlsafe_b64decode


# ------------------------------------------------------------
# DB
# ------------------------------------------------------------
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "users.db")


def _ensure_db_dir():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


def get_db() -> sqlite3.Connection:
    _ensure_db_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id            TEXT PRIMARY KEY,
            email         TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            tier          TEXT NOT NULL DEFAULT 'free',
            created_at    TEXT NOT NULL,
            last_login    TEXT
        );
        CREATE TABLE IF NOT EXISTS sessions (
            id            TEXT PRIMARY KEY,
            user_id       TEXT NOT NULL REFERENCES users(id),
            token_hash    TEXT NOT NULL,
            expires_at    TEXT NOT NULL,
            created_at    TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS payment_orders (
            id          TEXT PRIMARY KEY,
            user_id     TEXT NOT NULL,
            email       TEXT,
            order_type  TEXT NOT NULL DEFAULT 'pay',
            credential  TEXT,
            amount      TEXT,
            screenshot  TEXT,
            status      TEXT NOT NULL DEFAULT 'pending',
            created_at  TEXT NOT NULL,
            handled_at  TEXT
        );
        CREATE TABLE IF NOT EXISTS events (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    TEXT,
            device_id  TEXT,
            event      TEXT NOT NULL,
            meta       TEXT,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_events_event ON events(event, created_at);
        CREATE INDEX IF NOT EXISTS idx_events_user ON events(user_id, created_at);
    """)
    # 迁移：旧 users 表可能缺少 tier 列
    try:
        conn.execute("ALTER TABLE users ADD COLUMN tier TEXT NOT NULL DEFAULT 'free'")
    except sqlite3.OperationalError:
        pass  # 列已存在
    # 迁移：payment_orders 加 amount / screenshot 列（付费自动开通用）
    try:
        conn.execute("ALTER TABLE payment_orders ADD COLUMN amount TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE payment_orders ADD COLUMN screenshot TEXT")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()


# ------------------------------------------------------------
# Password hashing (bcrypt-free: PBKDF2 HMAC-SHA256)
# ------------------------------------------------------------
_SALT_LEN = 16
_ITERATIONS = 600_000
_DK_LEN = 32


def hash_password(password: str) -> str:
    salt = os.urandom(_SALT_LEN)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS, dklen=_DK_LEN)
    # Format: $pbkdf2-sha256$iterations$salt_b64$dk_b64
    return f"$pbkdf2-sha256${_ITERATIONS}${urlsafe_b64encode(salt).decode('ascii')}${urlsafe_b64encode(dk).decode('ascii')}"


def verify_password(password: str, hash_str: str) -> bool:
    try:
        _, algo, iterations, salt_b64, dk_b64 = hash_str.split("$")
        assert algo == "pbkdf2-sha256"
        salt = urlsafe_b64decode(salt_b64.encode("ascii"))
        expected = urlsafe_b64decode(dk_b64.encode("ascii"))
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iterations), dklen=len(expected))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


# ------------------------------------------------------------
# JWT (HMAC-SHA256, sym, no library needed)
# ------------------------------------------------------------
_JWT_SECRET = os.environ.get("JWT_SECRET")
if not _JWT_SECRET:
    _CONFIG_LOCAL = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.local.py")
    if os.path.exists(_CONFIG_LOCAL):
        try:
            import importlib.util as _iu
            _spec = _iu.spec_from_file_location("config_local", _CONFIG_LOCAL)
            _cfg = _iu.module_from_spec(_spec)
            _spec.loader.exec_module(_cfg)
            _JWT_SECRET = getattr(_cfg, "JWT_SECRET", "")
        except Exception:
            pass
    if not _JWT_SECRET:
        _JWT_SECRET = "dev-secret-change-in-production-@2026"
_JWT_ALGO = "HS256"
_JWT_EXP_HOURS = 72  # 3 days


def _b64url_encode(data: bytes) -> str:
    return urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    # pad back
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return urlsafe_b64decode(s)


def create_token(user: dict) -> str:
    """Create JWT for a user row (dict)."""
    header = _b64url_encode(json.dumps({"alg": _JWT_ALGO, "typ": "JWT"}).encode())
    now = int(time.time())
    payload = _b64url_encode(json.dumps({
        "sub": user["id"],
        "email": user["email"],
        "tier": user["tier"],
        "iat": now,
        "exp": now + _JWT_EXP_HOURS * 3600,
    }).encode())
    sig_raw = f"{header}.{payload}"
    sig = _b64url_encode(hmac.new(_JWT_SECRET.encode(), sig_raw.encode(), hashlib.sha256).digest())
    return f"{header}.{payload}.{sig}"


def verify_token(token: str) -> dict | None:
    """Verify JWT, return payload dict or None."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header_b64, payload_b64, sig_b64 = parts
        sig_raw = f"{header_b64}.{payload_b64}"
        expected_sig = _b64url_encode(hmac.new(
            _JWT_SECRET.encode(), sig_raw.encode(), hashlib.sha256
        ).digest())
        if not hmac.compare_digest(sig_b64.encode(), expected_sig.encode()):
            return None
        payload = json.loads(_b64url_decode(payload_b64))
        if payload.get("exp", 0) < time.time():
            return None
        return {"user_id": payload["sub"], "email": payload["email"], "tier": payload["tier"]}
    except Exception:
        return None


# ------------------------------------------------------------
# User CRUD
# ------------------------------------------------------------
def create_user(email: str, password: str) -> dict | None:
    """Create a new user. Returns user dict or None if email exists."""
    conn = get_db()
    try:
        uid = str(uuid.uuid4())
        now = _now_iso()
        conn.execute(
            "INSERT INTO users (id, email, password_hash, tier, created_at) VALUES (?,?,?,?,?)",
            (uid, email.lower().strip(), hash_password(password), "free", now),
        )
        conn.commit()
        return {"id": uid, "email": email.lower().strip(), "tier": "free", "created_at": now}
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def authenticate(email: str, password: str) -> dict | None:
    """Authenticate user, update last_login, return user dict or None."""
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email.lower().strip(),)).fetchone()
        if not row:
            return None
        if not verify_password(password, row["password_hash"]):
            return None
        now = _now_iso()
        conn.execute("UPDATE users SET last_login = ? WHERE id = ?", (now, row["id"]))
        conn.commit()
        return dict(row)
    finally:
        conn.close()


def get_user_by_id(user_id: str) -> dict | None:
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_user_tier(user_id: str, tier: str) -> bool:
    """直接改用户 tier。返回是否命中。"""
    conn = get_db()
    try:
        cur = conn.execute("UPDATE users SET tier = ? WHERE id = ?", (tier, user_id))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# ------------------------------------------------------------
# Payment orders（付费升级 + 邀请码升级）
# ------------------------------------------------------------
def create_payment_order(user_id: str, email: str, order_type: str, credential: str,
                         amount: float | None = None, screenshot: str | None = None,
                         auto_confirm: bool = False) -> dict:
    """建订单。invite 或 auto_confirm 直接 confirmed（邀请码即支付确认 / 付费自动开通），
    否则 pay 类型 pending 待人工核对。"""
    conn = get_db()
    try:
        oid = str(uuid.uuid4())
        now = _now_iso()
        status = "confirmed" if (order_type == "invite" or auto_confirm) else "pending"
        handled = now if status == "confirmed" else None
        conn.execute(
            "INSERT INTO payment_orders (id, user_id, email, order_type, credential, amount, screenshot, status, created_at, handled_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (oid, user_id, email, order_type, credential, amount, screenshot, status, now, handled),
        )
        conn.commit()
        return {"id": oid, "user_id": user_id, "email": email, "order_type": order_type,
                "credential": credential, "amount": amount, "screenshot": screenshot,
                "status": status, "created_at": now, "handled_at": handled}
    finally:
        conn.close()


def get_payment_order(order_id: str) -> dict | None:
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM payment_orders WHERE id = ?", (order_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_payment_orders(status: str | None = None) -> list:
    conn = get_db()
    try:
        if status:
            rows = conn.execute(
                "SELECT * FROM payment_orders WHERE status = ? ORDER BY created_at DESC", (status,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM payment_orders ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def confirm_payment_order(order_id: str) -> dict | None:
    """确认付费订单：升级用户 tier 并标记 confirmed。返回订单或 None。"""
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM payment_orders WHERE id = ?", (order_id,)).fetchone()
        if not row:
            return None
        if row["status"] == "pending":
            conn.execute("UPDATE users SET tier = 'pro' WHERE id = ?", (row["user_id"],))
            conn.execute(
                "UPDATE payment_orders SET status = 'confirmed', handled_at = ? WHERE id = ?",
                (_now_iso(), order_id),
            )
            conn.commit()
        return dict(conn.execute("SELECT * FROM payment_orders WHERE id = ?", (order_id,)).fetchone())
    finally:
        conn.close()


def reject_payment_order(order_id: str) -> dict | None:
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM payment_orders WHERE id = ?", (order_id,)).fetchone()
        if not row:
            return None
        conn.execute(
            "UPDATE payment_orders SET status = 'rejected', handled_at = ? WHERE id = ?",
            (_now_iso(), order_id),
        )
        conn.commit()
        return dict(conn.execute("SELECT * FROM payment_orders WHERE id = ?", (order_id,)).fetchone())
    finally:
        conn.close()


def revoke_payment_order(order_id: str) -> dict | None:
    """撤销已开通订单：若订单 confirmed，把用户 tier 降回 free，订单标记 revoked。
    安全阀：白嫖防护的核心在事后收不收得回来。"""
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM payment_orders WHERE id = ?", (order_id,)).fetchone()
        if not row:
            return None
        if row["status"] == "confirmed":
            conn.execute(
                "UPDATE users SET tier = 'free' WHERE id = ? AND tier = 'pro'",
                (row["user_id"],),
            )
            conn.execute(
                "UPDATE payment_orders SET status = 'revoked', handled_at = ? WHERE id = ?",
                (_now_iso(), order_id),
            )
            conn.commit()
        return dict(conn.execute("SELECT * FROM payment_orders WHERE id = ?", (order_id,)).fetchone())
    finally:
        conn.close()


def record_event(user_id: str | None, device_id: str | None, event: str, meta: dict | None = None) -> None:
    """写入一条埋点事件。失败静默（埋点不能拖垮主流程）。"""
    try:
        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO events (user_id, device_id, event, meta, created_at) VALUES (?,?,?,?,?)",
                (user_id, device_id, event,
                 json.dumps(meta, ensure_ascii=False) if meta else None,
                 _now_iso()),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass


def query_events(event: str | None = None, since: str | None = None, limit: int = 200) -> list:
    """查询埋点事件（管理端用）。"""
    conn = get_db()
    try:
        sql = "SELECT * FROM events"
        conds, args = [], []
        if event:
            conds.append("event = ?")
            args.append(event)
        if since:
            conds.append("created_at >= ?")
            args.append(since)
        if conds:
            sql += " WHERE " + " AND ".join(conds)
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        rows = conn.execute(sql, args).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# Auto-init on import
init_db()
