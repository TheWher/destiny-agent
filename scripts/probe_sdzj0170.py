# -*- coding: utf-8 -*-
"""识典 SDZJ0170《新锓希夷陈先生紫微斗数全书》抓取 + 指纹验证"""
import json, os, re, requests, urllib.parse

OUT = r"D:\OH-WorkSpace\Destiny_agent\tmp_sdzj0170"
os.makedirs(OUT, exist_ok=True)

URLS = {
    "v1_taiwei":  "https://www.shidianguji.com/book/SDZJ0170/chapter/1jvzoopnqo0t6",
    "v2_gufu":    "https://www.shidianguji.com/book/SDZJ0170/chapter/1jvzootg40y05",
    "v3_anxing":  "https://www.shidianguji.com/book/SDZJ0170/chapter/1jvzooy7dkbhh",
    "v4_lun":     "https://www.shidianguji.com/book/SDZJ0170/chapter/1jvzop13hw26h",
    "v5_tanxing": "https://www.shidianguji.com/book/SDZJ0170/chapter/1jvzop58rvdbm",
    "mingtu":     "https://www.shidianguji.com/book/SDZJ0170/chapter/1jvzop88fgrvp",
    "v7_huotao":  "https://www.shidianguji.com/book/SDZJ0170/chapter/1jvzop9sm7ygj",
}

# 抓取
resp = requests.post("http://127.0.0.1:11235/crawl",
                     json={"urls": list(URLS.values())}, timeout=300)
data = resp.json()
texts = {}
for res in data["results"]:
    name = [k for k, u in URLS.items() if u == res["url"]][0]
    texts[name] = res.get("markdown") or ""
    with open(os.path.join(OUT, f"{name}.md"), "w", encoding="utf-8") as f:
        f.write(texts[name])
    print(f"[save] {name}: {len(texts[name])} chars, success={res['success']}")

full = "\n".join(texts.values())
full_clean = re.sub(r"\[.*?\]\(.*?\)", "", full)  # 去链接

print(f"\n=== 总字符（含壳）: {len(full_clean)} ===")

FINGERPRINTS = {
    # 古籍层组 6 条（传统字形整句）
    "古1 祿逢沖破吉處藏凶": "祿逢沖破",
    "古2 星臨廟旺再觀生剋之機": "生剋之機",
    "古3 諸凶最宜制克": "最宜制克",
    "古4 辨生剋制化以定窮通": "辨生剋制化",
    "古5 命身相克心亂不閑": "命身相克",
    "古6 相貌加刑殺刑剋難免": "刑剋難免",
    # 简体组 3 条
    "简1 禄逢冲破吉处藏凶": "禄逢冲破，吉处藏凶",
    "简2 夹昌夹曲主贵兮": "夹昌夹曲主贵兮",
    "简3 生克制化之机": "生克制化之机",
    # 关键单字字形观察
    "字 衝(繁体)": "衝",
    "字 冲(简体)": "冲",
    "字 剋(繁体)": "剋",
    "字 克(简体)": "克",
    "字 佈(繁体)": "佈",
    "字 布(简体)": "布",
    "字 異體-祿": "祿",
    "字 簡體-禄": "禄",
}

print("=== 指纹/字形验证（在去壳全文中的出现次数）===")
for label, pat in FINGERPRINTS.items():
    cnt = full_clean.count(pat)
    print(f"{label}: {cnt} 次")
