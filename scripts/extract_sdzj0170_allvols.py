# -*- coding: utf-8 -*-
"""SDZJ0170 全卷数据层抓取+解析：从 raw HTML 的 _ROUTER_DATA.paragraphList 提取
fuwen/zhuwen/pianming，输出分卷 JSON。渲染层(md)是简体转写，数据层(JSON)是繁体保真。
"""
import re, json, os, sys, time, urllib.request

BASE = "https://www.shidianguji.com/book/SDZJ0170/chapter/"
OUT = r"D:\OH-WorkSpace\Destiny_agent\tmp_sdzj0170\full"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

# 卷入口 ID + 子章共享前缀（公共前缀 >= PREFIX_LEN 视为本卷子章）
VOLUMES = [
    ("v1", "1jvzoopnqo0t6", "1jvzoopn"),
    ("v3", "1jvzooy7dkbhh", "1jvzooy7"),
    ("v4", "1jvzop13hw26h", "1jvzop13"),
    ("v5", "1jvzop58rvdbm", "1jvzop58"),
    ("v7", "1jvzop9sm7ygj", "1jvzop9s"),
    ("mingtu", "1jvzop88fgrvp", "1jvzop88"),
]
PREFIX_LEN = 9  # 共享前缀长度阈值

def fetch(url, retry=3):
    for i in range(retry):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Referer": "https://www.shidianguji.com/book/SDZJ0170",
                "Accept-Language": "zh-CN,zh;q=0.9",
            })
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            if i == retry - 1:
                raise
            time.sleep(2 * (i + 1))

def enumerate_chapters(entry_id, prefix, entry_html):
    ids = set(re.findall(r'/chapter/([0-9a-z]+)', entry_html))
    mine = sorted(i for i in ids if i.startswith(prefix))
    if entry_id not in mine:
        mine.insert(0, entry_id)
    return mine

def find_json_key(obj, key):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key:
                return v
            r = find_json_key(v, key)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = find_json_key(v, key)
            if r is not None:
                return r
    return None

def parse_paragraphs(html):
    m = re.search(r'window\._ROUTER_DATA\s*=', html)
    if not m:
        return None
    j = html.find("{", m.start())
    dec = json.JSONDecoder()
    data, _ = dec.raw_decode(html[j:])
    plist = find_json_key(data, "paragraphList")
    if plist is None:
        return None
    fw, zw, jm = [], [], []
    for p in plist:
        content = p.get("content") or ""
        if not content.startswith("{"):
            continue
        try:
            inner = json.loads(content)
        except Exception:
            continue
        for line in inner.get("lines", []):
            lt = line.get("lineType")
            c = (line.get("content") or "").strip()
            if not c:
                continue
            if lt == 1:
                fw.append(c)
            elif lt == 2:
                zw.append(c)
            elif lt == 9:
                jm.append(c)
    return fw, zw, jm

def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for tag, entry_id, prefix in VOLUMES:
        if only and tag != only:
            continue
        print(f"\n=== {tag} 入口 {entry_id} ===")
        entry_html = fetch(BASE + entry_id)
        # 存入口 raw
        with open(os.path.join(OUT, f"{tag}_raw_{entry_id}.html"), "w", encoding="utf-8") as f:
            f.write(entry_html)
        chaps = enumerate_chapters(entry_id, prefix, entry_html)
        print(f"子章 {len(chaps)}: {chaps}")
        all_fw, all_zw, all_jm = [], [], []
        for cid in chaps:
            fn = os.path.join(OUT, f"{tag}_raw_{cid}.html")
            if not os.path.exists(fn):
                html = fetch(BASE + cid)
                with open(fn, "w", encoding="utf-8") as f:
                    f.write(html)
            else:
                html = open(fn, encoding="utf-8").read()
            parsed = parse_paragraphs(html)
            if parsed is None:
                print(f"  [{cid}] 无 paragraphList，跳过")
                continue
            fw, zw, jm = parsed
            all_fw += fw; all_zw += zw; all_jm += jm
            print(f"  [{cid}] 赋文{len(fw)} 注文{len(zw)} 篇名{len(jm)}")
            time.sleep(0.3)
        out = os.path.join(OUT, f"{tag}_zhujie_extract.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump({"fuwen": all_fw, "zhuwen": all_zw, "pianming": all_jm},
                      f, ensure_ascii=False, indent=1)
        fw_chars = sum(len(c) for c in all_fw)
        zw_chars = sum(len(c) for c in all_zw)
        print(f"  => {tag}: 赋文{len(all_fw)}条/{fw_chars}字 注文{len(all_zw)}条/{zw_chars}字 "
              f"篇名{len(all_jm)} -> {os.path.basename(out)}")

if __name__ == "__main__":
    main()
