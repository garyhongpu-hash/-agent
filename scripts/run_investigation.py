"""End-to-end test: scrape a website and generate a customer report."""

import asyncio
import json
import sys

from sales_agent.scraper.website import scrape_website
from sales_agent.agent.researcher import analyze_company


async def main():
    url = sys.argv[1] if len(sys.argv) > 1 else "https://www.flexport.com"
    print(f"🔍 正在抓取网站: {url}")

    scraped = await scrape_website(url)
    print(f"✅ 抓取完成: 首页 + {len(scraped.pages)} 个子页面")
    print(f"   首页标题: {scraped.homepage.title}")
    for p in scraped.pages:
        print(f"   子页面: {p.title} ({p.url})")

    print(f"\n📊 正在生成客户背景调查报告...")
    report = await analyze_company(scraped)

    print(f"\n{'='*60}")
    print(f"📋 客户背景调查报告")
    print(f"{'='*60}")
    print(json.dumps(report.model_dump(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
