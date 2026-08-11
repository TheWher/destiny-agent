#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Obsidian vault → 项目知识库 单向同步脚本（方案 B：私有仓 → 项目仓）

源：Obsidian vault（私有仓备份 whole vault，真源）
目标：Destiny_agent/knowledge_base/obsidian/（进公开项目仓，供检索模块读取，派生副本）

设计：
- 单向：真源在私有仓，本脚本只做 复制（源→目标），绝不做反向
- 白名单：只同步 md 文件（素材/笔记/MOC/模板），.obsidian、.canvas、图片附件不入库
- 排除清单：EXCLUDE 里的文件/目录跳过（含生辰/私密的笔记、King 手写区未来加这里）
- 幂等：目标目录每次全量重建，保证目标 = 源快照
- 运行：python scripts/sync_obsidian_to_kb.py [--vault <vault路径>]
"""
import os
import shutil
import sys

VAULT = r'D:\OBsidian\Ku\Learn'
TARGET = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'knowledge_base', 'obsidian',
)

# 排除：相对 vault 根的路径（正斜杠）。含私密内容的文件、King 手写区未来加这里。
EXCLUDE = {
    '笔记/来因宫.md',  # 含 King 生辰（2005-08-19），进公开仓前需去标识或 King 拍板
    '.gitignore',      # 私有仓专用，不入项目仓
}

SKIP_DIRS = {'.obsidian', '.obsidian-kb', '.git'}
SKIP_EXTS = {'.canvas'}


def sync():
    if os.path.exists(TARGET):
        shutil.rmtree(TARGET)
    count = 0
    for root, dirs, files in os.walk(VAULT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        rel_root = os.path.relpath(root, VAULT).replace(os.sep, '/')
        for f in files:
            rel = f'{rel_root}/{f}' if rel_root != '.' else f
            ext = os.path.splitext(f)[1]
            if ext in SKIP_EXTS or rel in EXCLUDE:
                continue
            if any(rel.startswith(e.rstrip('/') + '/') for e in EXCLUDE if e.endswith('/')):
                continue
            src = os.path.join(root, f)
            dst_dir = os.path.join(TARGET, rel_root)
            os.makedirs(dst_dir, exist_ok=True)
            shutil.copy2(src, os.path.join(dst_dir, f))
            count += 1
    print(f'[sync] {count} files -> {TARGET}')
    print('[sync] 真源=私有仓 vault；本目标为派生副本，勿直接编辑')


if __name__ == '__main__':
    if '--vault' in sys.argv:
        VAULT = sys.argv[sys.argv.index('--vault') + 1]
    sync()
