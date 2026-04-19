from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    sender: Literal["me", "other"] = Field(
        ..., description="消息发送者：'me' 表示自己（气泡靠右绿色），'other' 表示对方（靠左白色）"
    )
    sender_name: str | None = Field(
        default=None, description="可选，群聊时显示的发送者姓名"
    )
    content: str = Field(..., description="消息文字内容")
    timestamp: str | None = Field(
        default=None, description="消息时间，建议格式 HH:MM，例如 '10:30'"
    )


class ChatConversation(BaseModel):
    contact_name: str = Field(..., description="顶部显示的联系人或群组名称")
    contact_status: str | None = Field(
        default=None, description="联系人状态，如 'online' 或 'last seen today at 10:30'"
    )
    messages: list[ChatMessage] = Field(default_factory=list, description="按顺序排列的聊天消息列表")


class ScreenshotRequest(BaseModel):
    text: str = Field(..., description="用户粘贴的原始混合文字，可能包含对话和其他描述")
    contact_name: str | None = Field(
        default=None, description="可选，覆盖从文本中解析出的联系人名称"
    )
    width: int = Field(default=420, ge=320, le=1080, description="输出图片宽度（像素）")
    phone_style: Literal["iphone", "android", "none"] = Field(
        default="iphone",
        description="手机外壳样式：iphone（带 Dynamic Island）/ android（带挖孔）/ none（仅聊天区域）",
    )


class ExtractResponse(BaseModel):
    conversation: ChatConversation
