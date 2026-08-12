# -*- coding: utf-8 -*-
"""补抓 SDZJ0170 全部缺失 raw HTML + 全量解析数据层，输出分卷 JSON + 繁体保真统计"""
import re, json, os, time, urllib.request

BASE = "https://www.shidianguji.com/book/SDZJ0170/chapter/"
OUT = r"D:\OH-WorkSpace\Destiny_agent\tmp_sdzj0170\full"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

ALL_IDS = [
    "1jvzoopnqo0t6","1jvzootg40y05","1jvzootg41an9","1jvzootg41nad","1jvzootg41zxh",
    "1jvzootg42ckl","1jvzootg42p7p","1jvzootg431ut","1jvzootg43ehx","1jvzootg43r51",
    "1jvzootg443s5","1jvzootg44gf9","1jvzooy7dkbhh","1jvzop13hw26h","1jvzop13hwetl",
    "1jvzop13hwrgp","1jvzop13hx43t","1jvzop13hxgqx","1jvzop13hxte1","1jvzop13hy615",
    "1jvzop13hyio9","1jvzop13hyvbd","1jvzop13hz7yh","1jvzop13hzkll","1jvzop13hzx8p",
    "1jvzop58rvdbm","1jvzop58rvpyq","1jvzop88fgrvp","1jvzop88fh4it","1jvzop88fhh5x",
    "1jvzop88fhtt1","1jvzop88fi6g5","1jvzop88fij39","1jvzop88fivqd","1jvzop88fj8dh",
    "1jvzop88fjl0l","1jvzop88fjxnp","1jvzop88fkaat","1jvzop8d7olyq","1jvzop8d7oylu",
    "1jvzop8d7pb8y","1jvzop8d7pnw2","1jvzop8d7q0j6","1jvzop8d7qd6a","1jvzop8d7qpte",
    "1jvzop8d7r2gi","1jvzop8d7rf3m","1jvzop8d7rrqq","1jvzop8d7s4du","1jvzop8d7sh0y",
    "1jvzop8d7sto2","1jvzop8d7t6b6","1jvzop8d7tiya","1jvzop8d7tvle","1jvzop8d7u88i",
    "1jvzop8d7ukvm","1jvzop8d7uxiq","1jvzop8d7va5u","1jvzop8fn322b","1jvzop8fn3epf",
    "1jvzop8fn3rcj","1jvzop8fn43zn","1jvzop8fn4gmr","1jvzop8fn4t9v","1jvzop8fn55wz",
    "1jvzop8fn5ik3","1jvzop8fn5v77","1jvzop8fn67ub","1jvzop8fn6khf","1jvzop8fn6x4j",
    "1jvzop8fn79rn","1jvzop8fn7mer","1jvzop8fn7z1v","1jvzop9sm7ygj","1jvzop9sm8b3n",
    "1jvzop9sm90dv","1jvzopa1f8umz","1jvzopa1fayhn","1l8c31cc86psj",
]

def vol_tag(cid):
    if cid.startswith("1jvzoopn"): return "v1"
    if cid.startswith("1jvzootg4"): return "v2"
    if cid.startswith("1jvzooy7"): return "v3"
    if cid.startswith("1jvzop13"): return "v4"
    if cid.startswith("1jvzop58"): return "v5"
    if cid.startswith(("1jvzop88", "1jvzop8d", "1jvzop8f")): return "mingtu"
    if cid.startswith(("1jvzop9s", "1jvzopa1")): return "v7"
    if cid.startswith("1l8c31"): return "catalog"
    return "other"

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
    # 1) 补抓缺失 raw
    to_fetch = []
    for cid in ALL_IDS:
        tag = vol_tag(cid)
        fn = os.path.join(OUT, f"{tag}_raw_{cid}.html")
        if not os.path.exists(fn):
            to_fetch.append((tag, cid))
    print(f"需补抓 {len(to_fetch)} 页")
    for i, (tag, cid) in enumerate(to_fetch):
        try:
            html = fetch(BASE + cid)
            fn = os.path.join(OUT, f"{tag}_raw_{cid}.html")
            with open(fn, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"[{i+1}/{len(to_fetch)}] {tag} {cid} len={len(html)}")
        except Exception as e:
            print(f"[{i+1}/{len(to_fetch)}] {tag} {cid} ERR {e}")
        time.sleep(0.3)

    # 2) 全量解析
    vols = {}
    for cid in ALL_IDS:
        tag = vol_tag(cid)
        fn = os.path.join(OUT, f"{tag}_raw_{cid}.html")
        if not os.path.exists(fn):
            continue
        html = open(fn, encoding="utf-8").read()
        parsed = parse_paragraphs(html)
        if parsed is None:
            continue
        fw, zw, jm = parsed
        vols.setdefault(tag, {"fuwen": [], "zhuwen": [], "pianming": []})
        vols[tag]["fuwen"] += fw
        vols[tag]["zhuwen"] += zw
        vols[tag]["pianming"] += jm

    # 3) 输出 JSON + 统计
    pairs = [("殺","杀"), ("㐫","凶"), ("隂","陰"), ("郷","鄉"), ("祿","禄"),
             ("衝","冲"), ("剋","克"), ("賦","赋"), ("隨","随"), ("鬥","斗")]
    print("\n=== 分卷统计 ===")
    for tag, d in sorted(vols.items()):
        fw_chars = sum(len(c) for c in d["fuwen"])
        zw_chars = sum(len(c) for c in d["zhuwen"])
        out = os.path.join(OUT, f"{tag}_zhujie_extract.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
        alltext = "".join(d["fuwen"]) + "".join(d["zhuwen"])
        stats = " ".join(f"{a}:{alltext.count(a)}/{b}:{alltext.count(b)}" for a, b in pairs)
        print(f"{tag}: 赋文{len(d['fuwen'])}条/{fw_chars}字 注文{len(d['zhuwen'])}条/{zw_chars}字 | {stats}")

if __name__ == "__main__":
    main()
