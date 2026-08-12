# -*- coding: utf-8 -*-
"""从卷2 raw HTML 的 _ROUTER_DATA JSON 解析段落数据，提取注文"""
import re, json, os, glob

OUT = r"D:\OH-WorkSpace\Destiny_agent\tmp_sdzj0170\full"
V2_IDS = ["1jvzootg40y05","1jvzootg41an9","1jvzootg41nad","1jvzootg41zxh",
          "1jvzootg42ckl","1jvzootg42p7p","1jvzootg431ut","1jvzootg43ehx",
          "1jvzootg43r51","1jvzootg443s5","1jvzootg44gf9"]

def find_json_key(obj, key, path=""):
    """递归找 key 对应的值"""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key:
                return v
            r = find_json_key(v, key, path + "/" + k)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            r = find_json_key(v, key, path + f"[{i}]")
            if r is not None:
                return r
    return None

all_fw, all_zw, all_jm = [], [], []
for cid in V2_IDS:
    fn = os.path.join(OUT, f"v2_raw_{cid}.html")
    if not os.path.exists(fn):
        print(f"[skip] {cid} no html")
        continue
    html = open(fn, encoding="utf-8").read()
    m = re.search(r'window\._ROUTER_DATA\s*=', html)
    if not m:
        print(f"[fail] {cid} no router data")
        continue
    j = html.find("{", m.start())
    try:
        dec = json.JSONDecoder()
        data, end = dec.raw_decode(html[j:])
    except Exception as e:
        print(f"[json err] {cid}: {e}")
        continue
    plist = find_json_key(data, "paragraphList")
    if plist is None:
        print(f"[no plist] {cid}")
        continue
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
    all_fw += fw; all_zw += zw; all_jm += jm
    print(f"[{cid}] 赋文{len(fw)} 注文{len(zw)} 篇名{len(jm)}")

trad = set("長生帝旺郷則謀為無順遂較體興學國門開關萬與動對從時會歲臺龍鳳貴賓貝買賣銀錢業華歡聽靈雲霧電風車馬鳥魚艷豐農種園陽陰際億師歸當燈營號車軍陣陳階隊隨離舊書風雲氣見變體學頭點畫華萬靈電對從與時會貴銀豐")
def has_trad(s):
    return any(ch in trad for ch in s)

print("\n=== 汇总 ===")
print("赋文:", len(all_fw), "注文:", len(all_zw), "篇名:", len(all_jm))
print("注文含繁体:", sum(1 for c in all_zw if has_trad(c)), "/", len(all_zw))
print("赋文含繁体:", sum(1 for c in all_fw if has_trad(c)), "/", len(all_fw))
print("\n注文样本(前10):")
for c in all_zw[:10]:
    print("  ", c[:100])
print("\n赋文含繁体样本:")
for c in [c for c in all_fw if has_trad(c)][:5]:
    print("  ", c[:100])

out = os.path.join(OUT, "v2_zhujie_extract.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump({"fuwen": all_fw, "zhuwen": all_zw, "pianming": all_jm}, f, ensure_ascii=False, indent=1)
print("\nsaved:", out, "注文字符:", sum(len(c) for c in all_zw))
