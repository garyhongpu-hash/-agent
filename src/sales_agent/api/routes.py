from fastapi import APIRouter, HTTPException, Response

from sales_agent.agent.researcher import analyze_company
from sales_agent.models.report import CompanyReport
from sales_agent.models.request import InvestigateRequest
from sales_agent.scraper.website import scrape_website
from sales_agent.whatsapp.models import ExtractResponse, ScreenshotRequest
from sales_agent.whatsapp.parser import extract_conversation
from sales_agent.whatsapp.renderer import render_conversation

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


@router.post("/whatsapp/extract", response_model=ExtractResponse)
async def whatsapp_extract(req: ScreenshotRequest):
    """从混合文字中提取聊天对话结构（调试/预览用）。"""
    try:
        conv = await extract_conversation(req.text, req.contact_name)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"对话解析失败: {e}")
    return ExtractResponse(conversation=conv)


@router.post("/whatsapp/screenshot")
async def whatsapp_screenshot(req: ScreenshotRequest):
    """从混合文字生成 WhatsApp 风格聊天截图（PNG）。"""
    try:
        conv = await extract_conversation(req.text, req.contact_name)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"对话解析失败: {e}")
    if not conv.messages:
        raise HTTPException(status_code=422, detail="未能从输入中识别到聊天对话")
    png = render_conversation(conv, width=req.width)
    return Response(content=png, media_type="image/png")
