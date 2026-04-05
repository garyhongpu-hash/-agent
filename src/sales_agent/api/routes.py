from fastapi import APIRouter, HTTPException

from sales_agent.agent.researcher import analyze_company
from sales_agent.models.report import CompanyReport
from sales_agent.models.request import InvestigateRequest
from sales_agent.scraper.website import scrape_website

router = APIRouter(prefix="/api/v1")


@router.get("/health")
async def health_check():
    return {"status": "ok"}


@router.post("/investigate", response_model=CompanyReport)
async def investigate(request: InvestigateRequest):
    """输入目标客户公司官网，输出客户背景调查报告。"""
    url = str(request.url)

    try:
        scraped = await scrape_website(url)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"网站抓取失败: {e}")

    if not scraped.homepage.markdown.strip():
        raise HTTPException(status_code=422, detail="无法从该网站提取有效内容")

    try:
        report = await analyze_company(scraped)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI分析失败: {e}")

    return report
