# -*- coding: utf-8 -*-
"""南阳堂注解补提：抓卷2 子章 raw HTML，解析数据层，提取注文(lineType:2)，验证繁体保真"""
import asyncio, os, re, json, glob
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode

OUT = r"D:\OH-WorkSpace\Destiny_agent\tmp_sdzj0170\full"
V2_IDS = ["1jvzootg40y05","1jvzootg41an9","1jvzootg41nad","1jvzootg41zxh",
          "1jvzootg42ckl","1jvzootg42p7p","1jvzootg431ut","1jvzootg43ehx",
          "1jvzootg43r51","1jvzootg443s5","1jvzootg44gf9"]

def parse_html(html):
    """从 raw HTML 提取 (lineType, content) 行"""
    rows = []
    for m in re.finditer(r'paragraphId.*?content.:.(.*?)\},"startPageId"', html):
        blob = m.group(1)
        # 解一层转义后找 lines
        unesc = blob.replace('\\"', '"')
        for lm in re.finditer(r'lineType.:(\d+).*?content.:"([^"]*)"', unesc):
            lt, content = int(lm.group(1)), lm.group(2)
            if content.strip():
                rows.append((lt, content))
    return rows

async def main():
    crawler = AsyncWebCrawler(verbose=False)
    await crawler.start()
    cfg = CrawlerRunConfig(cache_mode=CacheMode.BYPASS, page_timeout=90000)

    all_rows = []
    for cid in V2_IDS:
        fn = os.path.join(OUT, f"v2_raw_{cid}.html")
        if os.path.exists(fn) and os.path.getsize(fn) > 100000:
            html = open(fn, encoding="utf-8").read()
            print(f"[cache] {cid} html={len(html)}")
        else:
            for attempt in range(5):
                res = await crawler.arun(url=f"https://www.shidianguji.com/book/SDZJ0170/chapter/{cid}", config=cfg)
                html = res.html or ""
                if len(html) > 100000:
                    open(fn, "w", encoding="utf-8").write(html)
                    print(f"[grab] {cid} html={len(html)} attempt={attempt+1}")
                    break
                else:
                    print(f"[retry] {cid} len={len(html)} attempt={attempt+1}")
                    await asyncio.sleep(4)
            else:
                print(f"[FAIL] {cid}")
                continue
        rows = parse_html(html)
        all_rows.extend(rows)
        print(f"  {cid}: {len(rows)} 行 (赋文{sum(1 for r in rows if r[0]==1)} 注文{sum(1 for r in rows if r[0]==2)} 卷名{sum(1 for r in rows if r[0]==4)} 篇名{sum(1 for r in rows if r[0]==9)})")

    await crawler.close()

    # 汇总
    fw = [c for lt, c in all_rows if lt == 1]
    zw = [c for lt, c in all_rows if lt == 2]
    jm = [c for lt, c in all_rows if lt == 9]
    trad = "長生帝旺郷則謀為無順遂較體興學國門開關萬與動對從時會歲臺龍鳳貴賓貝買賣銀錢業華歡聽靈雲霧電風車馬鳥魚艷豐農種園陽陰際億師歸當燈營號車軍陣陳階隊隨離舊書風雲氣見變體學頭點畫點華萬靈電動對從與舊歸時會歲貴賓銀錢華豐園陽陰際億"
    trad += "長生帝旺郷則謀為無順遂較體興學國門開關萬與動對從時會歲臺龍鳳貴賓貝買賣銀錢業華歡聽靈雲霧電風車馬鳥魚艷豐農種園陽陰際億師歸當燈營號車軍陣陳階隊隨離舊"

    print("\n=== 卷2 数据层汇总 ===")
    print("赋文行:", len(fw), "| 注文行:", len(zw), "| 篇名:", len(jm))
    zt = sum(1 for c in zw if any(ch in trad for ch in c))
    ft = sum(1 for c in fw if any(ch in trad for ch in c))
    print("注文含繁体:", zt, "/", len(zw), "| 赋文含繁体:", ft, "/", len(fw))
    print("\n注文样本:")
    for c in zw[:8]:
        print("  ", c[:90])
    print("\n赋文样本:")
    for c in fw[:4]:
        print("  ", c[:90])

    # 保存
    with open(os.path.join(OUT, "v2_zhujie_extract.json"), "w", encoding="utf-8") as f:
        json.dump({"fuwen": fw, "zhuwen": zw, "pianming": jm}, f, ensure_ascii=False, indent=1)
    print("\n已存 v2_zhujie_extract.json")

asyncio.run(main())
