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
    """)
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
_JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-in-production-@2026")
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


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# Auto-init on import
init_db()
