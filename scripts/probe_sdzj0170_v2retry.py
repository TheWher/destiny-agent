# -*- coding: utf-8 -*-
"""SDZJ0170 卷2 前4子章重试（限流空态）"""
import asyncio, os, re
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

OUT = r"D:\OH-WorkSpace\Destiny_agent\tmp_sdzj0170\full"

async def main():
    crawler = AsyncWebCrawler(verbose=False)
    await crawler.start()
    cfg = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS, page_timeout=90000,
        markdown_generator=DefaultMarkdownGenerator(
            content_filter=PruningContentFilter(threshold=0.30, threshold_type="fixed", min_word_threshold=0)
        ),
    )
    for cid in ["1jvzootg40y05", "1jvzootg41an9", "1jvzootg41nad", "1jvzootg41zxh"]:
        for attempt in range(5):
            res = await crawler.arun(url=f"https://www.shidianguji.com/book/SDZJ0170/chapter/{cid}", config=cfg)
            md = res.markdown or ""
            if len(md) > 100:
                with open(os.path.join(OUT, f"v2_sub_{cid}.md"), "w", encoding="utf-8") as f:
                    f.write(md)
                head = re.sub(r"\s+", " ", md[:120])
                print(f"[OK] {cid} len={len(md)} attempt={attempt+1} :: {head[:70]}")
                break
            else:
                print(f"[retry] {cid} empty len={len(md)} attempt={attempt+1}")
                await asyncio.sleep(4)
    await crawler.close()

asyncio.run(main())
