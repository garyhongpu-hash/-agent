from sales_agent.models.report import (
    CompanyOverview,
    CompanyReport,
    FinancialIndicators,
    ImportExportProfile,
    KeyPeople,
    KeyPerson,
    NewsItem,
    PainPointsAnalysis,
    ProductOrService,
    ProductsAndServices,
    RecentNews,
    SalesApproachStrategy,
    SocialMediaPresence,
)
from sales_agent.models.request import InvestigateRequest


def test_investigate_request_valid():
    req = InvestigateRequest(url="https://example.com")
    assert str(req.url) == "https://example.com/"


def test_company_report_full():
    report = CompanyReport(
        company_overview=CompanyOverview(
            company_name="Acme Corp",
            industry="制造业",
            headquarters="美国纽约",
            founded_year="2010",
            employee_count="100-500人",
            website="https://acme.com",
            description="一家专注于工业零部件的制造企业",
        ),
        products_and_services=ProductsAndServices(
            items=[
                ProductOrService(
                    name="工业阀门",
                    description="高压工业阀门",
                    target_market="北美",
                )
            ],
            summary="主营工业阀门及相关配件",
        ),
        key_people=KeyPeople(
            people=[KeyPerson(name="John Doe", title="CEO")],
            notes="管理层公开信息有限",
        ),
        financial_indicators=FinancialIndicators(
            revenue_estimate="约5000万美元",
            public_or_private="非上市",
            summary="中型企业，财务状况稳健",
        ),
        recent_news=RecentNews(
            items=[NewsItem(title="Acme发布新产品", summary="推出新一代阀门")],
            summary="近期有产品更新动态",
        ),
        import_export_profile=ImportExportProfile(
            trade_regions=["北美", "欧洲"],
            certifications=["ISO 9001"],
            import_export_hints="有从亚洲采购零部件的迹象",
            summary="活跃的国际贸易企业",
        ),
        social_media_presence=SocialMediaPresence(
            linkedin="https://linkedin.com/company/acme",
            summary="LinkedIn活跃度中等",
        ),
        pain_points_analysis=PainPointsAnalysis(
            pain_points=["供应链成本上升"],
            needs=["寻找性价比更高的供应商"],
            opportunities=["可提供有竞争力的报价"],
            summary="存在明确的供应商替换需求",
        ),
        sales_approach_strategy=SalesApproachStrategy(
            recommended_approach="通过LinkedIn联系采购负责人",
            talking_points=["强调产品质量认证", "突出成本优势"],
            potential_objections=["现有供应商关系稳定"],
            timing_suggestions="建议在Q1采购季前联系",
            summary="建议以产品质量+成本优势为切入点",
        ),
        confidence_note="公司概览和产品信息已确认；财务数据为推断",
    )
    assert report.company_overview.company_name == "Acme Corp"
    # Verify JSON serialization round-trip
    json_str = report.model_dump_json()
    restored = CompanyReport.model_validate_json(json_str)
    assert restored.company_overview.company_name == "Acme Corp"


def test_company_report_json_schema():
    schema = CompanyReport.model_json_schema()
    assert "properties" in schema
    assert "company_overview" in schema["properties"]
