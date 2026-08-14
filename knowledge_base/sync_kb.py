# -*- coding: utf-8 -*-
"""Obsidian 知识库双向同步脚本。

主 vault: D:\OBsidian\Ku\Learn（King 打开的 Obsidian）
项目副本: <repo>/knowledge_base/obsidian（检索模块读取）

冲突规则（King 2026-08-14 拍板）：按修改时间，新的覆盖旧的。
用法：python sync_kb.py [--dry-run]
"""
import os, sys, shutil

VAULT = r"D:\OBsidian\Ku\Learn"
REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "obsidian")
SKIP_DIRS = {".git", ".obsidian", "__pycache__", ".trash"}
EXTS = {".md"}

def collect(root):
    files = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if os.path.splitext(fn)[1] in EXTS:
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, root)
                files[rel] = full
    return files

def sync(a_root, b_root, dry):
    a = collect(a_root)
    b = collect(b_root)
    all_keys = set(a) | set(b)
    actions = []
    for k in sorted(all_keys):
        in_a, in_b = k in a, k in b
        if in_a and in_b:
            ta, tb = os.path.getmtime(a[k]), os.path.getmtime(b[k])
            if ta > tb:
                actions.append(("A->B", k))
            elif tb > ta:
                actions.append(("B->A", k))
        elif in_a:
            actions.append(("A->B(new)", k))
        else:
            actions.append(("B->A(new)", k))
    for direction, k in actions:
        src = a[k] if direction.startswith("A") else b[k]
        dst = os.path.join(b_root if direction.startswith("A") else a_root, k)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if dry:
            print(f"[dry] {direction} {k}")
        else:
            shutil.copy2(src, dst)
            print(f"[ok] {direction} {k}")
    if not actions:
        print("两侧一致，无需同步")
    return len(actions)

if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    print(f"主 vault: {VAULT}")
    print(f"项目副本: {REPO}")
    n = sync(VAULT, REPO, dry)
    # 反向（B 独有的补到 A）
    n += sync(REPO, VAULT, dry)
    print(f"done, {n} actions")
