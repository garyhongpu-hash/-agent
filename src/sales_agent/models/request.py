from pydantic import BaseModel, Field, HttpUrl


class InvestigateRequest(BaseModel):
    url: HttpUrl = Field(description="目标客户公司官网URL")
