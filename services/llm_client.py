#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""LLM API 客户端 — DeepSeek Anthropic 兼容端点

API Key 三层回退：环境变量 → ~/.claude/settings.json → config.local.py
"""

import json
import os
import time
import requests
import importlib.util

# ============================================================
# API 配置（三层回退）
# ============================================================

API_CONFIG = {}

# 1) 环境变量（云平台标准方式）
for key, env_var in [
    ("base_url", "ANTHROPIC_BASE_URL"),
    ("api_key", "ANTHROPIC_AUTH_TOKEN"),
    ("model", "ANTHROPIC_MODEL"),
]:
    val = os.environ.get(env_var, "")
    if val:
        API_CONFIG[key] = val

# 2) settings.json（本地开发回退）
if not API_CONFIG.get("api_key") or not API_CONFIG.get("model"):
    SETTINGS_PATH = os.path.join(os.path.expanduser("~"), ".claude", "settings.json")
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                settings = json.load(f)
            env = settings.get("env", {})
            API_CONFIG.setdefault("base_url", env.get("ANTHROPIC_BASE_URL", "https://api.deepseek.com/anthropic"))
            API_CONFIG.setdefault("api_key", env.get("ANTHROPIC_AUTH_TOKEN", ""))
            API_CONFIG.setdefault("model", env.get("ANTHROPIC_MODEL", "deepseek-v4-pro[1m]"))
        except Exception:
            pass

# 3) config.local.py（项目级配置，优先级最高）
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_LOCAL = os.path.join(_ROOT, "config.local.py")
if os.path.exists(CONFIG_LOCAL):
    try:
        spec = importlib.util.spec_from_file_location("config_local", CONFIG_LOCAL)
        cfg = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cfg)
        for k in ("base_url", "model", "api_key"):
            v = getattr(cfg, "API_CONFIG", {}).get(k, "")
            if v:
                API_CONFIG[k] = v
    except Exception:
        pass


def _call_api(system_prompt: str, messages: list[dict], max_tokens: int,
             temperature: float, timeout: int, stop_sequences: list = None) -> dict:
    """单次 API 调用，含空内容重试"""
    url = f"{API_CONFIG['base_url']}/v1/messages"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": API_CONFIG["api_key"],
        "anthropic-version": "2023-06-01",
    }
    payload = {
        "model": API_CONFIG["model"],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "thinking": {"type": "disabled"},
        "system": system_prompt,
        "messages": messages,
    }
    if stop_sequences:
        payload["stop_sequences"] = stop_sequences

    # 兜底轮（GLM/bigmodel 兼容层实证 2026-09-09）：带 stop_sequences 时偶发只回 thinking
    # 块无 text 块（且无视 thinking:disabled），非确定性，产线反复踩中。第 3 轮去掉
    # stop_sequences 重试，成功后客户端按序列截断——与服务端截停等价语义，对 DeepSeek 透明。
    use_stop = bool(stop_sequences)
    attempts = 3 if use_stop else 2
    for attempt in range(attempts):
        if attempt == 2 and use_stop:
            payload.pop("stop_sequences", None)
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
            if resp.status_code != 200:
                err_text = resp.text[:500]
                return {"success": False, "error": f"API 返回错误 ({resp.status_code}): {err_text}"}

            data = resp.json()
            text = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    text += block["text"]

            if text:
                if attempt == 2 and use_stop:
                    for _s in stop_sequences:
                        if _s in text:
                            text = text.split(_s)[0]
                return {
                    "success": True,
                    "text": text,
                    "model": data.get("model", API_CONFIG["model"]),
                    "usage": data.get("usage", {}),
                }

            if attempt < attempts - 1:
                time.sleep(3)
                continue

            usage = data.get("usage", {})
            stop_reason = data.get("stop_reason", "unknown")
            return {"success": False, "error": f"API 返回空内容（stop={stop_reason}），已重试{attempts - 1}次仍失败"}

        except requests.Timeout:
            if attempt < attempts - 1:
                time.sleep(3)
                continue
            return {"success": False, "error": f"API 调用超时（{timeout}秒），已重试仍失败"}
        except Exception as e:
            if attempt < attempts - 1:
                time.sleep(3)
                continue
            return {"success": False, "error": f"API 调用失败: {str(e)}"}

    return {"success": False, "error": "API 调用失败：所有重试均未成功"}



def _call_api_stream(system_prompt: str, messages: list[dict], max_tokens: int,
                     temperature: float, timeout: int):
    """流式 API 调用，yield SSE data: 行"""
    url = f"{API_CONFIG['base_url']}/v1/messages"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": API_CONFIG["api_key"],
        "anthropic-version": "2023-06-01",
    }
    payload = {
        "model": API_CONFIG["model"],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "thinking": {"type": "disabled"},
        "system": system_prompt,
        "messages": messages,
        "stream": True,
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout, stream=True)
        if resp.status_code != 200:
            yield f"data: {json.dumps({'error': f'API {resp.status_code}'})}\n\n"
            return
        for line in resp.iter_lines():
            if not line: continue
            line = line.decode("utf-8") if isinstance(line, bytes) else line
            if line.startswith("data: "):
                yield f"{line}\n\n"
    except requests.Timeout:
        yield f"data: {json.dumps({'error': '超时'})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"


