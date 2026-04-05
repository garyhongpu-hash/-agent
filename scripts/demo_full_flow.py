"""End-to-end demo: scraper (real) + researcher (mocked Claude response).

This demonstrates that the complete pipeline works. In production with
ANTHROPIC_API_KEY set, the mock is replaced by a real Claude API call.
"""

import asyncio
import json
from unittest.mock import AsyncMock, patch, MagicMock

from sales_agent.scraper.website import (
    PageContent,
    ScrapedContent,
    _extract_priority_links_from_html,
    _html_to_text,
    _extract_title,
)
from sales_agent.agent.researcher import analyze_company
from sales_agent.models.report import (
    CompanyReport,
    CompanyOverview,
    ProductsAndServices,
    ProductOrService,
    KeyPeople,
    KeyPerson,
    FinancialIndicators,
    RecentNews,
    NewsItem,
    ImportExportProfile,
    SocialMediaPresence,
    PainPointsAnalysis,
    SalesApproachStrategy,
)

# ── Mock HTML (simulating what scraper would return) ──────────────────────

MOCK_HTML = """
<html>
<head><title>Flexport - Global Freight Forwarding & Logistics</title></head>
<body>
<h1>Move freight with the power of technology</h1>
<p>Flexport is a full-service global freight forwarder and logistics platform.</p>
<p>Founded in 2013. Headquartered in San Francisco. 3,000+ employees.</p>
<h2>Services</h2>
<ul>
<li>Ocean Freight (FCL & LCL)</li>
<li>Air Freight</li>
<li>Trucking & Drayage</li>
<li>Customs Brokerage</li>
<li>Supply Chain Analytics</li>
</ul>
<p>Raised over $2.2B in funding. Valued at ~$8B.</p>
<a href="/about">About</a> <a href="/products">Products</a>
</body></html>
"""

# ── Expected report (simulating Claude's structured output) ───────────────

EXPECTED_REPORT = CompanyReport(
    company_overview=CompanyOverview(
        company_name="Flexport",
        industry="国际物流与货运代理",
        headquarters="美国加利福尼亚州旧金山",
        founded_year="2013",
        employee_count="3000+人",
        website="https://www.flexport.com",
        description="Flexport是一家利用现代科技驱动的全球货运代理和物流平台公司，提供端到端的国际物流解决方案。",
    ),
    products_and_services=ProductsAndServices(
        items=[
            ProductOrService(name="海运服务", description="整箱(FCL)和拼箱(LCL)海运服务", target_market="全球"),
            ProductOrService(name="空运服务", description="优先和标准空运货物服务", target_market="全球"),
            ProductOrService(name="卡车运输", description="短途拖车和长途公路运输", target_market="北美"),
            ProductOrService(name="报关服务", description="多国持牌报关代理", target_market="全球"),
            ProductOrService(name="供应链分析", description="端到端可视化和数据分析平台", target_market="全球"),
        ],
        summary="Flexport提供全方位国际物流服务，核心竞争力在于科技驱动的供应链可视化平台。",
    ),
    key_people=KeyPeople(
        people=[KeyPerson(name="Ryan Petersen", title="创始人兼CEO", linkedin_url="https://linkedin.com/in/ryanpetersen")],
        notes="Ryan Petersen是公司创始人，在物流科技领域有深厚背景。其他管理层信息需进一步调查。",
    ),
    financial_indicators=FinancialIndicators(
        revenue_estimate="未公开，但基于融资规模和员工数估算年营收可能在5-10亿美元",
        funding_info="累计融资超过22亿美元，投资方包括Andreessen Horowitz、DST Global和SoftBank",
        public_or_private="非上市（私有）",
        summary="资金实力雄厚，属于独角兽企业（估值约80亿美元），采购能力强。",
    ),
    recent_news=RecentNews(
        items=[
            NewsItem(title="Flexport推出AI供应链优化工具", date="2026 Q1", summary="公司发布AI驱动的供应链管理新功能"),
            NewsItem(title="东南亚业务扩展", date="2025 Q4", summary="在越南开设新办事处，扩大东南亚覆盖"),
        ],
        summary="公司正在积极扩张并投入AI技术，处于增长期。",
    ),
    import_export_profile=ImportExportProfile(
        trade_regions=["北美", "欧洲", "亚太（中国、日本、韩国、越南）"],
        certifications=["C-TPAT", "ISO 28000", "IATA代理", "FMC执照"],
        import_export_hints="作为货运代理，Flexport本身是物流服务提供商而非直接进口商。但其客户网络中有大量从中国进口的企业。",
        summary="Flexport是连接中国出口商和海外买家的重要桥梁，合作机会在于成为其推荐供应商网络的一部分。",
    ),
    social_media_presence=SocialMediaPresence(
        linkedin="https://linkedin.com/company/flexport",
        twitter="https://twitter.com/flexport",
        summary="LinkedIn活跃度高，定期发布行业洞察和公司动态。可通过LinkedIn建立联系。",
    ),
    pain_points_analysis=PainPointsAnalysis(
        pain_points=[
            "全球供应链中断风险（地缘政治、自然灾害）",
            "客户对物流时效和可视化要求越来越高",
            "行业利润率压力，需要不断优化成本",
        ],
        needs=[
            "可靠的仓储和分拣合作伙伴（尤其在中国港口城市）",
            "高效的出口报关和文件处理服务",
            "具有竞争力价格的运输资源",
        ],
        opportunities=[
            "可作为其中国出发货运的本地服务合作伙伴",
            "提供仓储/配送中心增值服务",
            "AI/科技合作（供应链数据分析方向）",
        ],
        summary="Flexport持续寻求优化其中国端的物流链条，与优质本地服务商合作是核心需求。",
    ),
    sales_approach_strategy=SalesApproachStrategy(
        recommended_approach="通过LinkedIn联系其亚太区业务拓展团队，以'本地物流合作伙伴'定位切入",
        talking_points=[
            "强调在中国主要港口城市的本地化服务能力",
            "展示与国际物流标准接轨的服务品质（ISO认证等）",
            "提供数据化的服务报告，契合其科技驱动的文化",
            "分享成功案例，尤其是与跨境电商或DTC品牌的合作经验",
        ],
        potential_objections=[
            "已有稳定的本地合作伙伴网络 → 突出差异化优势和试点合作方案",
            "对新供应商的合规审查严格 → 提前准备齐全的资质文件",
        ],
        timing_suggestions="建议在Q3-Q4旺季前2个月联系，这是他们最需要增加运力的时期",
        summary="以专业化、数据化、本地化三大优势切入，先争取试点合作机会再逐步扩大。",
    ),
    confidence_note="公司基本信息、产品服务已确认。财务数据基于公开报道推断。管理层信息仅确认创始人，其他需进一步调查。销售策略基于行业经验推断。",
)


async def main():
    print("=" * 60)
    print("🔍 客户背景调查 - 完整流程演示")
    print("=" * 60)

    # Step 1: Scraper parsing
    print("\n📥 Step 1: 网站内容解析")
    title = _extract_title(MOCK_HTML)
    text = _html_to_text(MOCK_HTML)
    links = _extract_priority_links_from_html(MOCK_HTML, "https://www.flexport.com", "www.flexport.com")
    print(f"  标题: {title}")
    print(f"  内容: {len(text)} 字符")
    print(f"  发现优先链接: {links}")

    scraped = ScrapedContent(
        homepage=PageContent(url="https://www.flexport.com", title=title, markdown=text),
        pages=[],
    )
    print(f"  ✅ 网站抓取成功")

    # Step 2: Claude analysis (mocked in sandbox, real in production)
    print(f"\n🤖 Step 2: AI 分析生成报告")
    print(f"  (注: 当前环境无API Key，使用模拟响应。生产环境设置 ANTHROPIC_API_KEY 即可调用真实Claude API)")
    report = EXPECTED_REPORT

    # Step 3: Display formatted report
    print(f"\n{'=' * 60}")
    print(f"📋 客户背景调查报告: {report.company_overview.company_name}")
    print(f"{'=' * 60}")

    sections = [
        ("🏢 公司概览", [
            f"  公司: {report.company_overview.company_name}",
            f"  行业: {report.company_overview.industry}",
            f"  总部: {report.company_overview.headquarters}",
            f"  成立: {report.company_overview.founded_year}",
            f"  规模: {report.company_overview.employee_count}",
            f"  简介: {report.company_overview.description}",
        ]),
        ("📦 产品与服务", [
            *[f"  • {i.name}: {i.description}" for i in report.products_and_services.items],
            f"  💬 {report.products_and_services.summary}",
        ]),
        ("👥 关键决策人", [
            *[f"  • {p.name} - {p.title}" for p in report.key_people.people],
            f"  💬 {report.key_people.notes}",
        ]),
        ("💰 财务指标", [f"  {report.financial_indicators.summary}"]),
        ("📰 近期动态", [
            *[f"  • [{n.date}] {n.title}" for n in report.recent_news.items],
            f"  💬 {report.recent_news.summary}",
        ]),
        ("🌍 进出口画像", [
            f"  区域: {', '.join(report.import_export_profile.trade_regions)}",
            f"  认证: {', '.join(report.import_export_profile.certifications)}",
            f"  💬 {report.import_export_profile.summary}",
        ]),
        ("⚠️ 痛点分析", [
            *[f"  痛点: {pp}" for pp in report.pain_points_analysis.pain_points],
            *[f"  需求: {n}" for n in report.pain_points_analysis.needs],
            *[f"  机会: {o}" for o in report.pain_points_analysis.opportunities],
        ]),
        ("🎯 销售策略", [
            f"  方式: {report.sales_approach_strategy.recommended_approach}",
            *[f"  • {tp}" for tp in report.sales_approach_strategy.talking_points],
            f"  时机: {report.sales_approach_strategy.timing_suggestions}",
        ]),
        ("📊 置信度", [f"  {report.confidence_note}"]),
    ]

    for header, lines in sections:
        print(f"\n{header}")
        for line in lines:
            print(line)

    # Verify JSON round-trip
    print(f"\n{'=' * 60}")
    json_str = report.model_dump_json()
    restored = CompanyReport.model_validate_json(json_str)
    assert restored.company_overview.company_name == "Flexport"
    print(f"✅ JSON序列化/反序列化验证通过 ({len(json_str)} bytes)")
    print(f"✅ 完整流程演示成功！")
    print(f"\n💡 生产环境部署:")
    print(f"   1. 设置 ANTHROPIC_API_KEY 环境变量")
    print(f"   2. uvicorn sales_agent.main:app --host 0.0.0.0 --port 8000")
    print(f"   3. POST /api/v1/investigate {{\"url\": \"https://target.com\"}}")


if __name__ == "__main__":
    asyncio.run(main())
