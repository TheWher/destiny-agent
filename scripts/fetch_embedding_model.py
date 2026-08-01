#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""部署用：从 ModelScope 下载 bge-small-zh-v1.5 到 models/（embedding 后端上线前置）。

为什么 ModelScope：HuggingFace 直连/hf-mirror 在国内网络（尤其代理限速）下
极慢或超时，ModelScope 国内直链快（实测 91MB ~14s）。

用法：python scripts/fetch_embedding_model.py [目标目录]
默认目标目录：<项目根>/models/bge-small-zh-v1.5
已存在的文件跳过（重复执行幂等）。
"""
import json
import os
import pathlib
import sys

MODEL_ID = "AI-ModelScope/bge-small-zh-v1.5"
BASE = f"https://modelscope.cn/models/{MODEL_ID}/resolve/master"
FILES = [
    "config.json",
    "config_sentence_transformers.json",
    "modules.json",
    "sentence_bert_config.json",
    "special_tokens_map.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.txt",
    "model.safetensors",
    "1_Pooling/config.json",
]

PROJ = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_DIR = PROJ / "models" / "bge-small-zh-v1.5"


def main() -> int:
    target = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DIR
    target.mkdir(parents=True, exist_ok=True)

    # 探测模型仓库是否可达（失败直接报错，部署方需检查网络）
    import requests
    ok, fail = 0, 0
    for rel in FILES:
        out = target / rel
        if out.exists() and out.stat().st_size > 0:
            print(f"skip  {rel} (exists)")
            ok += 1
            continue
        url = f"{BASE}/{rel}"
        try:
            r = requests.get(url, timeout=300)
            r.raise_for_status()
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(r.content)
            print(f"ok    {rel} ({len(r.content)//1024}KB)")
            ok += 1
        except Exception as e:
            print(f"FAIL  {rel}: {e}")
            fail += 1
    print(f"\n{ok} ok / {fail} failed -> {target}")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
