from __future__ import annotations

import anthropic

from sales_agent.config import settings
from sales_agent.models.report import CompanyReport
from sales_agent.scraper.website import ScrapedContent

SYSTEM_PROMPT = """你是一位专业的外贸客户背景调查分析师。你的任务是根据提供的公司网站内容，生成一份详尽的客户背景调查报告。

## 你的分析原则

1. **基于事实**：所有结论必须基于提供的网站内容。如果某些信息无法从网站获取，请明确标注为"未找到"或"推断"。
2. **外贸视角**：从中国出口商的角度分析，重点关注该客户的采购需求、合作潜力和沟通策略。
3. **实用导向**：每个分析部分都应直接服务于销售决策，避免泛泛而谈。
4. **中文输出**：全部使用中文输出，专有名词可保留英文原文。

## 分析重点

- 公司规模和行业地位 → 判断采购能力
- 产品线和目标市场 → 找到供应契合点
- 管理层信息 → 确定联系对象
- 近期动态 → 把握联系时机
- 痛点分析 → 准备销售话术
- 进出口画像 → 评估合作可能性"""


async def analyze_company(scraped: ScrapedContent) -> CompanyReport:
    """Use Claude to analyze scraped website content and produce a report."""
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    context = scraped.to_context_string()

    response = await client.messages.create(
        model=settings.agent_model,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    f"请根据以下网站内容，生成一份完整的客户背景调查报告。\n\n"
                    f"目标公司网站: {scraped.homepage.url}\n\n"
                    f"--- 网站抓取内容 ---\n\n{context}"
                ),
            }
        ],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": CompanyReport.model_json_schema(),
            }
        },
    )

    # Parse the structured JSON response
    text = next(b.text for b in response.content if b.type == "text")
    return CompanyReport.model_validate_json(text)
