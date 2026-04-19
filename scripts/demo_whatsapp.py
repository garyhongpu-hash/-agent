"""Demo script: render a WhatsApp-style screenshot from a chat-like text file.

Usage:
    python scripts/demo_whatsapp.py [input.txt] [output.png]

If no input file is given, a built-in sample is used. The script will:
  1. Call Claude (if ANTHROPIC_API_KEY is set) to extract a ChatConversation.
  2. If no API key is available, fall back to a hand-built conversation so the
     renderer can still be exercised offline.
  3. Render the conversation as PNG and write it to the output path.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from sales_agent.config import settings
from sales_agent.whatsapp.models import ChatConversation, ChatMessage
from sales_agent.whatsapp.renderer import render_conversation

SAMPLE_TEXT = """这是今天跟 John Smith 的对话记录，仅供参考：

客户 (10:28): Hi, 有最新的报价吗？
我 (10:30): 您好，FOB 上海 USD 12/pc。
客户 (10:31): Can you do USD 10?
我 (10:32): 量大可以谈。需要多少数量？
客户 (10:34): 5000 pcs，年底之前交货。

（注：客户在美国西海岸，以下是后续整理的跟进事项……）
"""

FALLBACK_CONVERSATION = ChatConversation(
    contact_name="John Smith",
    contact_status="online",
    messages=[
        ChatMessage(sender="other", content="Hi, 有最新的报价吗？", timestamp="10:28"),
        ChatMessage(sender="me", content="您好，FOB 上海 USD 12/pc。", timestamp="10:30"),
        ChatMessage(sender="other", content="Can you do USD 10?", timestamp="10:31"),
        ChatMessage(
            sender="me",
            content="量大可以谈。需要多少数量？",
            timestamp="10:32",
        ),
        ChatMessage(sender="other", content="5000 pcs，年底之前交货。", timestamp="10:34"),
    ],
)


async def build_conversation(text: str) -> ChatConversation:
    if not settings.anthropic_api_key:
        print("[demo] 未设置 ANTHROPIC_API_KEY，使用内置 fallback 对话以便验证渲染。")
        return FALLBACK_CONVERSATION
    from sales_agent.whatsapp.parser import extract_conversation

    print("[demo] 调用 Claude 提取对话...")
    return await extract_conversation(text)


async def main() -> None:
    args = sys.argv[1:]
    in_path = Path(args[0]) if args else None
    out_path = Path(args[1]) if len(args) > 1 else Path("demo.png")

    text = in_path.read_text(encoding="utf-8") if in_path else SAMPLE_TEXT
    conv = await build_conversation(text)

    print(f"[demo] 对话: {conv.contact_name} ({len(conv.messages)} 条消息)")
    for m in conv.messages:
        print(f"  [{m.sender}] {m.timestamp or '--:--'}  {m.content}")

    png = render_conversation(conv, width=420)
    out_path.write_bytes(png)
    print(f"[demo] 已写入 {out_path} ({len(png)} bytes)")


if __name__ == "__main__":
    asyncio.run(main())
