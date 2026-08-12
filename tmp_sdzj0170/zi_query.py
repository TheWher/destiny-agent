# -*- coding: utf-8 -*-
"""查 zi.tools API（走代理）：㐫 隂 郷 殺 賦 隨 的異體/繁簡关系"""
import json, sys, urllib.request
sys.stdout.reconfigure(encoding="utf-8")

chars = ["㐫", "隂", "郷", "殺", "賦", "隨"]
proxy = urllib.request.ProxyHandler({"https": "http://127.0.0.1:7890", "http": "http://127.0.0.1:7890"})
opener = urllib.request.build_opener(proxy)

for ch in chars:
    url = "https://zi.tools/api/zi/" + urllib.parse.quote(ch)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with opener.open(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8"))
        print("=" * 60)
        print(f"字: {ch}")
        for k in ["kTotalStrokes", "kRSUnicode", "kMandarin", "kDefinition", "kSemanticVariant", "kZVariant"]:
            if k in data:
                v = data[k]
                if isinstance(v, (dict, list)):
                    v = json.dumps(v, ensure_ascii=False)[:400]
                print(f"  {k}: {v}")
    except Exception as e:
        print(f"{ch}: 查询失败 {e}")
