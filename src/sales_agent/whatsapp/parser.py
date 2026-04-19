from __future__ import annotations

import anthropic

from sales_agent.config import settings
from sales_agent.whatsapp.models import ChatConversation

SYSTEM_PROMPT = """你是一个聊天记录抽取助手。用户会给你一段文字，其中可能混合了背景描述、注释和聊天对话。

## 你的任务

1. 从输入中识别出聊天对话，忽略无关的背景描述、旁白、元信息、章节标题。
2. 推断每条消息的发送者视角：
   - "me" 表示"我"发送的消息（在截图中靠右、绿色气泡）。
   - "other" 表示对方发送的消息（在截图中靠左、白色气泡）。
   - 如果文本中有"我："、"I:"、"Me:"、"A:" 或第一人称表述，视为 "me"。
   - 如果没有明确的视角标记，将第一位说话的人视为 "other"，其余发言者视为 "me"。
3. 保留消息原文（含原语言、表情符号、标点），不要翻译或改写。
4. 如果消息附带时间戳，提取并规整为 "HH:MM" 格式；没有时间戳就留空。
5. 推断联系人名称：
   - 优先使用文本中明确指定的对方姓名。
   - 如果是群聊，填群组名称；没有就填 "WhatsApp Chat"。
6. 如果能推断联系人在线状态（如 "online"、"last seen..."），填入 contact_status；否则留空。

## 输出

严格按提供的 JSON Schema 输出，不要添加任何额外字段。如果文本中没有任何有效对话，messages 返回空列表。"""


async def extract_conversation(
    text: str, contact_name_override: str | None = None
) -> ChatConversation:
    """Use Claude structured output to pull a WhatsApp-style conversation out of mixed text."""
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    response = await client.messages.create(
        model=settings.agent_model,
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    "请从下列文字中识别出聊天对话并按 schema 输出。\n\n"
                    f"--- 原始文字 ---\n\n{text}"
                ),
            }
        ],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": ChatConversation.model_json_schema(),
            }
        },
    )

    text_block = next(b.text for b in response.content if b.type == "text")
    conversation = ChatConversation.model_validate_json(text_block)

    if contact_name_override:
        conversation.contact_name = contact_name_override

    return conversation
