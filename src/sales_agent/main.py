from fastapi import FastAPI

from sales_agent.api.routes import router

app = FastAPI(
    title="外贸客户背景调查 API",
    description="输入目标客户公司官网，AI自动生成客户背景调查报告",
    version="0.1.0",
)

app.include_router(router)
