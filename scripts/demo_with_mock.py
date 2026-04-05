"""Demo: simulate the full pipeline with mock HTML to verify the complete flow."""

import asyncio
import json

from sales_agent.scraper.website import (
    PageContent,
    ScrapedContent,
    _extract_priority_links_from_html,
    _html_to_text,
    _extract_title,
)
from sales_agent.agent.researcher import analyze_company

# Simulated HTML for Flexport
MOCK_HOMEPAGE_HTML = """
<html>
<head><title>Flexport - Global Freight Forwarding & Logistics</title></head>
<body>
<h1>Move freight with the power of technology</h1>
<p>Flexport is a full-service global freight forwarder and logistics platform using modern software to fix the user experience in global trade.</p>
<p>Founded in 2013 by Ryan Petersen, Flexport is headquartered in San Francisco, CA with offices in over 15 countries.</p>
<h2>Our Services</h2>
<ul>
<li>Ocean Freight: Full container load (FCL) and less than container load (LCL)</li>
<li>Air Freight: Priority and standard air cargo services</li>
<li>Trucking: Drayage and over-the-road transportation</li>
<li>Customs Brokerage: Licensed customs brokerage in multiple countries</li>
<li>Supply Chain Management: End-to-end visibility and analytics</li>
</ul>
<h2>Company Facts</h2>
<p>We serve over 10,000 clients worldwide. Our team of 3,000+ employees operates across Americas, Europe, and Asia-Pacific.</p>
<p>Flexport has raised over $2.2 billion in funding, including investments from Andreessen Horowitz, DST Global, and SoftBank.</p>
<a href="/about">About Us</a>
<a href="/products">Products</a>
<a href="/team">Leadership</a>
<a href="/contact">Contact</a>
<a href="/blog">Blog</a>
<a href="https://linkedin.com/company/flexport">LinkedIn</a>
</body>
</html>
"""

MOCK_ABOUT_HTML = """
<html>
<head><title>About Flexport</title></head>
<body>
<h1>About Flexport</h1>
<p>Flexport was founded in 2013 with a mission to make global trade easy for everyone. We're building the platform for global logistics, combining modern software and data analytics with trusted service.</p>
<p>Key milestones: IPO-track company, valued at approximately $8 billion as of last funding round.</p>
<p>Industry certifications: C-TPAT certified, ISO 28000, IATA agent, FMC licensed OTI.</p>
<h2>Global Presence</h2>
<p>Offices in: San Francisco, New York, Los Angeles, Chicago, Atlanta, Amsterdam, Hamburg, Shanghai, Shenzhen, Hong Kong, Seoul, Tokyo, Ho Chi Minh City.</p>
<h2>Recent News</h2>
<p>Q1 2026: Flexport launches AI-powered supply chain optimization tool</p>
<p>Q4 2025: Expanded operations in Southeast Asia with new Vietnam office</p>
<p>Q3 2025: Partnership with major retailers for holiday season logistics</p>
</body>
</html>
"""


async def main():
    print("=" * 60)
    print("🔍 Demo: 客户背景调查完整流程 (使用模拟数据)")
    print("=" * 60)

    # Step 1: Simulate scraping
    print("\n📥 Step 1: 网站内容解析...")
    homepage_text = _html_to_text(MOCK_HOMEPAGE_HTML)
    homepage_title = _extract_title(MOCK_HOMEPAGE_HTML)
    about_text = _html_to_text(MOCK_ABOUT_HTML)
    about_title = _extract_title(MOCK_ABOUT_HTML)

    links = _extract_priority_links_from_html(
        MOCK_HOMEPAGE_HTML, "https://www.flexport.com", "www.flexport.com"
    )
    print(f"   首页标题: {homepage_title}")
    print(f"   发现 {len(links)} 个优先链接: {links}")
    print(f"   首页内容: {len(homepage_text)} 字符")
    print(f"   About页面: {len(about_text)} 字符")

    scraped = ScrapedContent(
        homepage=PageContent(
            url="https://www.flexport.com",
            title=homepage_title,
            markdown=homepage_text,
        ),
        pages=[
            PageContent(
                url="https://www.flexport.com/about",
                title=about_title,
                markdown=about_text,
            ),
        ],
    )

    # Step 2: Generate report via Claude
    print(f"\n🤖 Step 2: Claude AI 分析中... (模型: claude-sonnet-4-6)")
    report = await analyze_company(scraped)

    # Step 3: Display report
    print(f"\n{'=' * 60}")
    print(f"📋 客户背景调查报告: {report.company_overview.company_name}")
    print(f"{'=' * 60}")

    print(f"\n--- 公司概览 ---")
    print(f"  公司: {report.company_overview.company_name}")
    print(f"  行业: {report.company_overview.industry}")
    print(f"  总部: {report.company_overview.headquarters}")
    print(f"  成立: {report.company_overview.founded_year}")
    print(f"  规模: {report.company_overview.employee_count}")
    print(f"  简介: {report.company_overview.description}")

    print(f"\n--- 产品与服务 ---")
    for item in report.products_and_services.items:
        print(f"  • {item.name}: {item.description}")
    print(f"  总结: {report.products_and_services.summary}")

    print(f"\n--- 关键决策人 ---")
    for person in report.key_people.people:
        print(f"  • {person.name} - {person.title}")
    print(f"  说明: {report.key_people.notes}")

    print(f"\n--- 财务指标 ---")
    print(f"  {report.financial_indicators.summary}")

    print(f"\n--- 进出口画像 ---")
    print(f"  贸易区域: {', '.join(report.import_export_profile.trade_regions)}")
    print(f"  认证: {', '.join(report.import_export_profile.certifications)}")
    print(f"  分析: {report.import_export_profile.summary}")

    print(f"\n--- 痛点分析 ---")
    for pp in report.pain_points_analysis.pain_points:
        print(f"  ⚠ {pp}")
    for need in report.pain_points_analysis.needs:
        print(f"  💡 {need}")

    print(f"\n--- 销售策略建议 ---")
    print(f"  方式: {report.sales_approach_strategy.recommended_approach}")
    print(f"  要点:")
    for tp in report.sales_approach_strategy.talking_points:
        print(f"    • {tp}")
    print(f"  时机: {report.sales_approach_strategy.timing_suggestions}")

    print(f"\n--- 置信度 ---")
    print(f"  {report.confidence_note}")

    # Also output full JSON
    print(f"\n{'=' * 60}")
    print(f"📄 完整JSON报告:")
    print(f"{'=' * 60}")
    print(json.dumps(report.model_dump(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
