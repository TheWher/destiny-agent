# -*- coding: utf-8 -*-
"""JWT_SECRET 解析序回归（2026-09-09 加固，DEPLOY_CHECKLIST 安全洞销账）。

铁律：禁止已知常量兜底（旧常量 "dev-secret-change-in-production-@2026" 入过 git，
知道仓库即可伪造 token）。解析序 = env → config.local.py → 持久化随机密钥。
"""
import os
import re
import models.user as mu

OLD_CONSTANT = "dev-secret-change-in-production-@2026"
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _resolve(monkeypatch, tmp_path, env_secret="", use_config=False, config_secret="",
             keyfile_content=None, break_makedirs=False):
    keyfile = tmp_path / "jwt_secret.key"
    if keyfile_content is not None:
        keyfile.write_text(keyfile_content, encoding="utf-8")
    cfg_path = tmp_path / "config.local.py"
    if use_config:
        cfg_path.write_text(f"JWT_SECRET = {config_secret!r}\n", encoding="utf-8")
    monkeypatch.setattr(mu, "_JWT_KEY_FILE", str(keyfile))
    monkeypatch.setattr(mu, "_CONFIG_LOCAL", str(cfg_path) if use_config else str(tmp_path / "absent.py"))
    monkeypatch.setenv("JWT_SECRET", env_secret)
    if break_makedirs:
        import builtins
        real_makedirs = os.makedirs

        def boom(*a, **k):
            raise OSError("read-only fs")
        monkeypatch.setattr(os, "makedirs", boom)
    return mu._resolve_jwt_secret(), keyfile


def test_env_secret_wins(monkeypatch, tmp_path):
    s, _ = _resolve(monkeypatch, tmp_path, env_secret="env-secret",
                    use_config=True, config_secret="cfg-secret", keyfile_content="file-secret")
    assert s == "env-secret"


def test_config_secret_beats_keyfile(monkeypatch, tmp_path):
    s, _ = _resolve(monkeypatch, tmp_path, use_config=True, config_secret="cfg-secret",
                    keyfile_content="file-secret")
    assert s == "cfg-secret"


def test_persisted_keyfile_reuse(monkeypatch, tmp_path):
    s, _ = _resolve(monkeypatch, tmp_path, keyfile_content="ab" * 32)
    assert s == "ab" * 32


def test_generate_and_persist_roundtrip(monkeypatch, tmp_path):
    s1, kf = _resolve(monkeypatch, tmp_path)
    assert HEX64.match(s1) and s1 != OLD_CONSTANT
    assert kf.exists() and kf.read_text(encoding="utf-8") == s1, "密钥必须持久化（重启 token 不失效）"
    # 模拟下次启动：清空后再解析应复用持久化值
    s2, _ = _resolve(monkeypatch, tmp_path, keyfile_content=kf.read_text(encoding="utf-8"))
    assert s2 == s1


def test_never_falls_back_to_known_constant(monkeypatch, tmp_path):
    s, _ = _resolve(monkeypatch, tmp_path)
    assert s != OLD_CONSTANT


def test_readonly_fs_degrades_to_inmemory_random(monkeypatch, tmp_path):
    s, kf = _resolve(monkeypatch, tmp_path, break_makedirs=True)
    assert HEX64.match(s) and s != OLD_CONSTANT
    assert not kf.exists(), "不可写时不得半写文件"
