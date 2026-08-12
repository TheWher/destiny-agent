# -*- coding: utf-8 -*-
"""SDZJ0170 卷2 子章抓取 + 卷4 子章枚举抓取"""
import asyncio, os, re
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

OUT = r"D:\OH-WorkSpace\Destiny_agent\tmp_sdzj0170\full"
os.makedirs(OUT, exist_ok=True)

def md_gen():
    return DefaultMarkdownGenerator(
        content_filter=PruningContentFilter(threshold=0.30, threshold_type="fixed", min_word_threshold=0)
    )

async def main():
    crawler = AsyncWebCrawler(verbose=False)
    await crawler.start()

    # 卷2 子章（已知 11 个）
    v2_ids = ["1jvzootg40y05","1jvzootg41an9","1jvzootg41nad","1jvzootg41zxh",
              "1jvzootg42ckl","1jvzootg42p7p","1jvzootg431ut","1jvzootg43ehx",
              "1jvzootg43r51","1jvzootg443s5","1jvzootg44gf9"]

    # 卷4 raw HTML 枚举子章
    cfg_html = CrawlerRunConfig(cache_mode=CacheMode.BYPASS, page_timeout=90000)
    res4 = await crawler.arun(url="https://www.shidianguji.com/book/SDZJ0170/chapter/1jvzop13hw26h", config=cfg_html)
    html4 = res4.html or ""
    v4_ids = sorted(set(re.findall(r'1jvzop13[0-9a-z]+', html4)))
    print("卷4 子章 ids:", len(v4_ids), v4_ids)

    # 抓取全部（卷2 子章 + 卷4 子章），低 threshold 防截断
    cfg = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS, page_timeout=90000,
        markdown_generator=md_gen(),
    )
    for tag, cid in [("v2", x) for x in v2_ids] + [("v4", x) for x in v4_ids]:
        url = f"https://www.shidianguji.com/book/SDZJ0170/chapter/{cid}"
        res = await crawler.arun(url=url, config=cfg)
        md = res.markdown or ""
        fn = os.path.join(OUT, f"{tag}_sub_{cid}.md")
        with open(fn, "w", encoding="utf-8") as f:
            f.write(md)
        # 标题首行
        head = re.sub(r"\s+", " ", md[:120])
        print(f"[{tag}] {cid}: ok={res.success} len={len(md)} :: {head[:80]}")
    await crawler.close()

asyncio.run(main())
