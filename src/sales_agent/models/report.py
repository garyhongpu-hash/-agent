from pydantic import BaseModel, Field


class CompanyOverview(BaseModel):
    company_name: str = Field(description="公司名称")
    industry: str = Field(description="所属行业")
    headquarters: str = Field(description="总部所在地")
    founded_year: str | None = Field(default=None, description="成立年份")
    employee_count: str | None = Field(default=None, description="员工规模（如：50-200人）")
    website: str = Field(description="公司官网URL")
    description: str = Field(description="公司简介（2-3句话）")


class ProductOrService(BaseModel):
    name: str = Field(description="产品/服务名称")
    description: str = Field(description="产品/服务描述")
    target_market: str | None = Field(default=None, description="目标市场")


class ProductsAndServices(BaseModel):
    items: list[ProductOrService] = Field(description="公司产品或服务列表")
    summary: str = Field(description="产品/服务总体分析")


class KeyPerson(BaseModel):
    name: str = Field(description="姓名")
    title: str = Field(description="职位")
    linkedin_url: str | None = Field(default=None, description="LinkedIn链接（如有）")


class KeyPeople(BaseModel):
    people: list[KeyPerson] = Field(description="关键决策人列表")
    notes: str = Field(description="关于决策层的补充说明")


class FinancialIndicators(BaseModel):
    revenue_estimate: str | None = Field(default=None, description="营收估算")
    funding_info: str | None = Field(default=None, description="融资信息")
    public_or_private: str | None = Field(default=None, description="上市/非上市")
    summary: str = Field(description="财务状况总体评估")


class NewsItem(BaseModel):
    title: str = Field(description="新闻标题")
    date: str | None = Field(default=None, description="日期")
    summary: str = Field(description="新闻摘要")


class RecentNews(BaseModel):
    items: list[NewsItem] = Field(description="近期新闻列表")
    summary: str = Field(description="新闻动态总结")


class ImportExportProfile(BaseModel):
    trade_regions: list[str] = Field(description="贸易区域（如：北美、欧洲等）")
    certifications: list[str] = Field(default_factory=list, description="相关认证（如：ISO, CE等）")
    import_export_hints: str = Field(description="进出口活动分析")
    summary: str = Field(description="贸易画像总结")


class SocialMediaPresence(BaseModel):
    linkedin: str | None = Field(default=None, description="LinkedIn主页链接")
    twitter: str | None = Field(default=None, description="Twitter/X链接")
    facebook: str | None = Field(default=None, description="Facebook链接")
    other_platforms: list[str] = Field(default_factory=list, description="其他社交平台")
    summary: str = Field(description="社交媒体存在感评估")


class PainPointsAnalysis(BaseModel):
    pain_points: list[str] = Field(description="识别到的痛点/挑战")
    needs: list[str] = Field(description="潜在需求")
    opportunities: list[str] = Field(description="合作机会")
    summary: str = Field(description="痛点与需求分析总结")


class SalesApproachStrategy(BaseModel):
    recommended_approach: str = Field(description="推荐的销售切入方式")
    talking_points: list[str] = Field(description="关键沟通要点")
    potential_objections: list[str] = Field(description="可能的异议及应对")
    timing_suggestions: str = Field(description="联系时机建议")
    summary: str = Field(description="销售策略总结")


class CompanyReport(BaseModel):
    company_overview: CompanyOverview = Field(description="公司概览")
    products_and_services: ProductsAndServices = Field(description="产品与服务")
    key_people: KeyPeople = Field(description="关键决策人")
    financial_indicators: FinancialIndicators = Field(description="财务指标")
    recent_news: RecentNews = Field(description="近期动态")
    import_export_profile: ImportExportProfile = Field(description="进出口画像")
    social_media_presence: SocialMediaPresence = Field(description="社交媒体")
    pain_points_analysis: PainPointsAnalysis = Field(description="痛点分析")
    sales_approach_strategy: SalesApproachStrategy = Field(description="销售策略建议")
    confidence_note: str = Field(
        description="信息置信度说明：哪些信息已确认，哪些为推断"
    )
