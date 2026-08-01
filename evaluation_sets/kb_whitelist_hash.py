#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""kb_whitelist.json 内容哈希的唯一算法源。

为什么需要这个文件：
  哈希值必须能被评测脚本可靠复现，否则启动时 fail fast 永远炸，或跳过比对形同虚设。
  算法不靠人记着复现，由本脚本唯一提供：评测脚本 import 它重算，名单生成也调它。

用法：
  python kb_whitelist_hash.py            # 打印当前文件的 content_hash
  python kb_whitelist_hash.py --check    # 校验文件内 content_hash 是否与重算一致（不一致返回码 1）
  python kb_whitelist_hash.py --update   # 用重算值回写 content_hash 字段
"""
import hashlib
import json
import pathlib
import sys

HASH_FIELDS = [
    "tiers",
    "schema_registered",
    "reachable_not_registered",
    "dry_run_rules",
    "dispatch_allowlist",
]

CANONICAL_JSON_KWARGS = {
    "ensure_ascii": False,   # 保留中文原样，不转 \uXXXX
    "sort_keys": True,       # 字段按 key 排序，与文件内书写顺序无关
    "separators": (",", ":"),  # compact：无多余空白
}


def load_whitelist(path: pathlib.Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def compute_content_hash(path: pathlib.Path) -> str:
    data = load_whitelist(path)
    semantic = {k: data[k] for k in HASH_FIELDS if k in data}
    canonical = json.dumps(semantic, **CANONICAL_JSON_KWARGS)
    return hashlib.sha1(canonical.encode("utf-8")).hexdigest()[:8]


def main() -> int:
    path = pathlib.Path(__file__).resolve().parent / "kb_whitelist.json"
    computed = compute_content_hash(path)

    # hash_scope 与 HASH_FIELDS 一致性自动校验（一一对应，防漂移）
    data_for_scope = load_whitelist(path)
    scope = data_for_scope.get("hash_scope")
    if scope is not None and scope != HASH_FIELDS:
        print(f"SCOPE MISMATCH: file hash_scope={scope} != HASH_FIELDS={HASH_FIELDS}")
        return 1

    if "--update" in sys.argv:
        data = load_whitelist(path)
        data["content_hash"] = computed
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"updated content_hash -> {computed}")
        return 0

    stored = load_whitelist(path).get("content_hash")
    print(f"computed: {computed}")
    if "--check" in sys.argv:
        if stored == computed:
            print("OK: content_hash matches")
            return 0
        print(f"MISMATCH: stored={stored}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
