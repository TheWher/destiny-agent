# -*- coding: utf-8 -*-
"""SDZJ0170 完整抓取：滚动加载页（卷2/卷4）+ 子页枚举（命图/卷7）"""
import asyncio, os, re, json
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

OUT = r"D:\OH-WorkSpace\Destiny_agent\tmp_sdzj0170\full"
os.makedirs(OUT, exist_ok=True)

SCROLL_JS = """
async () => {
  for (let i = 0; i < 10; i++) {
    window.scrollTo(0, document.body.scrollHeight);
    await new Promise(r => setTimeout(r, 700));
  }
}
"""

def md_gen():
    return DefaultMarkdownGenerator(
        content_filter=PruningContentFilter(threshold=0.48, threshold_type="fixed", min_word_threshold=0)
    )

async def grab(crawler, url, scroll=False):
    cfg = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        page_timeout=90000,
        markdown_generator=md_gen(),
    )
    if scroll:
        cfg.js_code = SCROLL_JS
    result = await crawler.arun(url=url, config=cfg)
    md = result.markdown if result.success else ""
    return md, result.success

async def main():
    proxy_config = None
    # 尝试直连；失败再用 Clash 代理
    try:
        crawler = AsyncWebCrawler(verbose=False)
        await crawler.start()
        # 卷2 / 卷4 滚动抓
        targets = {
            "v2_gufu_scroll": "https://www.shidianguji.com/book/SDZJ0170/chapter/1jvzootg40y05",
            "v4_lun_scroll": "https://www.shidianguji.com/book/SDZJ0170/chapter/1jvzop13hw26h",
            "mingtu_collect": "https://www.shidianguji.com/book/SDZJ0170/chapter/1jvzop88fgrvp",
            "v7_collect": "https://www.shidianguji.com/book/SDZJ0170/chapter/1jvzop9sm7ygj",
        }
        collected_links = {}
        for name, url in targets.items():
            md, ok = await grab(crawler, url, scroll=True)
            print(f"[grab] {name}: ok={ok} len={len(md)}")
            with open(os.path.join(OUT, name + ".md"), "w", encoding="utf-8") as f:
                f.write(md)
            # 收集章节子页链接
            links = set(re.findall(r"/book/SDZJ0170/chapter/([A-Za-z0-9]+)", md))
            collected_links[name] = links
            print(f"  subpage ids: {len(links)} -> {sorted(links)}")

        # 命图/卷7 子页抓取
        for name, links in collected_links.items():
            for cid in sorted(links):
                url = f"https://www.shidianguji.com/book/SDZJ0170/chapter/{cid}"
                md, ok = await grab(crawler, url, scroll=True)
                fn = f"{name}_sub_{cid}.md"
                with open(os.path.join(OUT, fn), "w", encoding="utf-8") as f:
                    f.write(md)
                print(f"[sub] {fn}: ok={ok} len={len(md)}")
        await crawler.close()
    except Exception as e:
        print("ERR:", e)
        try:
            await crawler.close()
        except Exception:
            pass

asyncio.run(main())
