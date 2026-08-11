#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""知识库入库脚本：抓取网页 → frontmatter 卫生校验 → 写入 vault 素材池

用法：
    python scripts/ingest_kb.py <json配置或内联参数>

校验前置（2026-08-11 mose 定）：入库前跑 frontmatter 卫生检查（tags 无重复无代码残留、
必填字段齐全），不合格拦下，校验放源头不放出口。

配置 JSON 示例：
[
  {
    "url": "https://example.com/page",
    "file": "2026-08-11-slug.md",
    "title": "页面标题",
    "source": "站点名",
    "authority": "官方",          # 古籍原文/百科/官方/个人站/本人确认
    "system": "",                 # 三合/飞星，跨体系术语必填
    "tags": ["素材", "紫微斗数"],
    "content_mode": "fit_markdown"  # fit_markdown 默认 / markdown 全文
  }
]
"""
import json
import re
import sys
import os
from datetime import datetime
from urllib import request

CRAWL_URL = 'http://127.0.0.1:11235/crawl'
VAULT_RAW_DIR = r'D:\OBsidian\Ku\Learn\素材池\网页快照'
_NOISE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ingest_noise_filters.json')


def _load_noise_filters() -> dict:
    """源站噪音过滤配置：域名 -> [{pattern, note}]（配置驱动，加源站只改配置不动代码）"""
    if not os.path.exists(_NOISE_FILE):
        return {}
    with open(_NOISE_FILE, encoding='utf-8') as f:
        return json.load(f)


def _host_of(url: str) -> str:
    return url.split('/')[2].replace('www.', '') if '//' in url else url


def apply_noise_filters(url: str, text: str) -> str:
    """按域名应用噪音过滤正则（整串匹配，宁可少滤不可错滤）"""
    filters = _load_noise_filters()
    rules = filters.get(_host_of(url), [])
    for rule in rules:
        text = re.sub(rule['pattern'], '', text)
    return text

REQUIRED_FIELDS = ['title', 'url', 'source', 'fetched_at', 'status', 'type', 'content_mode']
CODE_LEAK_PATTERN = re.compile(r'\.TrimEnd\(\)|\.strip\(\)|Out-String|ForEach-Object|\$it\.|to_json|replace\(', re.I)


def validate_frontmatter(fm: dict, tags: list) -> list:
    """frontmatter 卫生检查，返回错误列表（空=合格）"""
    errors = []
    for f in REQUIRED_FIELDS:
        if not fm.get(f):
            errors.append(f'缺必填字段: {f}')
    if not tags:
        errors.append('tags 为空')
    seen = set()
    for t in tags:
        t = t.strip()
        if not t:
            errors.append('tags 含空项')
        elif t in seen:
            errors.append(f'tags 重复: {t}')
        seen.add(t)
        if CODE_LEAK_PATTERN.search(t):
            errors.append(f'tags 含代码残留: {t}')
    fm_text = json.dumps(fm, ensure_ascii=False)
    if CODE_LEAK_PATTERN.search(fm_text):
        errors.append('frontmatter 含代码残留')
    return errors


def crawl(url: str) -> dict:
    req = request.Request(CRAWL_URL, data=json.dumps({'urls': [url]}).encode(),
                          headers={'Content-Type': 'application/json'})
    with request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read())
    return data['results'][0]


def build_frontmatter(cfg: dict, fetched_at: str, content_mode: str) -> str:
    tags = cfg['tags']
    # 去重保序 + 强制带 素材
    seen = []
    for t in ['素材'] + tags:
        t = t.strip()
        if t and t not in seen:
            seen.append(t)
    lines = ['---']
    for k in ['title', 'url', 'source']:
        lines.append(f'{k}: {cfg[k]}')
    lines.append(f'fetched_at: {fetched_at}')
    lines.append('status: raw')
    lines.append(f'authority: {cfg.get("authority", "")}')
    lines.append(f'system: {cfg.get("system", "")}')
    lines.append('tags:')
    lines += [f'  - {t}' for t in seen]
    lines.append('type: 网页快照')
    lines.append(f'content_mode: {content_mode}')
    lines.append('---')
    return '\n'.join(lines)


def ingest(cfg: dict, dry_run: bool = False):
    res = crawl(cfg['url'])
    if not res.get('success'):
        print(f"FAIL {cfg['file']}: 抓取失败 {res.get('error')}")
        return False
    mode = cfg.get('content_mode', 'fit_markdown')
    content = res.get('fit_markdown') if mode == 'fit_markdown' else res.get('markdown')
    # 源站噪音过滤（版权尾巴/广告，按域名配置）
    content = apply_noise_filters(cfg['url'], content)
    fetched_at = datetime.now().strftime('%Y-%m-%dT%H:%M:%S%z')
    fm = {
        'title': cfg['title'], 'url': cfg['url'], 'source': cfg['source'],
        'fetched_at': fetched_at, 'status': 'raw', 'type': '网页快照',
        'content_mode': mode,
    }
    errors = validate_frontmatter(fm, cfg['tags'])
    if errors:
        print(f"FAIL {cfg['file']}: frontmatter 卫生校验不过 -> {errors}")
        return False
    md = build_frontmatter(cfg, fetched_at, mode) + '\n\n' + content
    path = os.path.join(VAULT_RAW_DIR, cfg['file'])
    if dry_run:
        print(f"OK(dry) {cfg['file']} ({len(md)} chars)")
        return True
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(md)
    print(f"OK {cfg['file']} ({len(md)} chars)")
    return True


def clean_files(paths: list):
    """重洗/清洗：只对正文应用噪音过滤，frontmatter 原样保留（fetched_at 永不覆盖），
    加 cleaned_at 记录清洗时间。与重新抓取（ingest）分清：抓取时间稳定，操作记录可查。"""
    ok = True
    for p in paths:
        if not os.path.exists(p):
            print(f"SKIP {p}: 不存在")
            ok = False
            continue
        text = open(p, encoding='utf-8').read()
        m = re.match(r'^(---\n.*?\n---\n)(.*)$', text, re.DOTALL)
        if not m:
            print(f"SKIP {p}: 无 frontmatter")
            ok = False
            continue
        fm_block, body = m.group(1), m.group(2)
        fm = {}
        for line in fm_block.splitlines():
            if ':' in line and not line.startswith('-'):
                k, v = line.split(':', 1)
                fm[k.strip()] = v.strip().strip('"')
        url = fm.get('url', '')
        new_body = apply_noise_filters(url, body)
        cleaned_at = datetime.now().strftime('%Y-%m-%dT%H:%M:%S%z')
        # frontmatter 更新 cleaned_at（保留原 fetched_at）
        if 'cleaned_at' in fm_block:
            fm_block = re.sub(r'(?m)^cleaned_at:.*$', f'cleaned_at: {cleaned_at}', fm_block)
        else:
            fm_block = fm_block.rstrip('\n') + f'\ncleaned_at: {cleaned_at}\n---\n'
        with open(p, 'w', encoding='utf-8', newline='\n') as f:
            f.write(fm_block + new_body)
        print(f"CLEAN {os.path.basename(p)} (fetched_at 保留: {fm.get('fetched_at', '?')})")
    return ok


def main():
    if '--clean' in sys.argv:
        idx = sys.argv.index('--clean')
        paths = sys.argv[idx + 1:]
        sys.exit(0 if clean_files(paths) else 1)
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cfg_path = sys.argv[1]
    dry_run = '--dry-run' in sys.argv
    with open(cfg_path, encoding='utf-8') as f:
        cfgs = json.load(f)
    ok = all(ingest(c, dry_run) for c in cfgs)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
