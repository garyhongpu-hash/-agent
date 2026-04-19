from io import BytesIO

from PIL import Image

from sales_agent.whatsapp.models import ChatConversation, ChatMessage
from sales_agent.whatsapp.renderer import render_conversation


def _sample_conversation() -> ChatConversation:
    return ChatConversation(
        contact_name="John Smith",
        contact_status="online",
        messages=[
            ChatMessage(sender="other", content="Hi, 有最新的报价吗？", timestamp="10:28"),
            ChatMessage(sender="me", content="您好，FOB 上海 USD 12/pc。", timestamp="10:30"),
            ChatMessage(sender="other", content="Can you do USD 10?", timestamp="10:31"),
            ChatMessage(
                sender="me",
                content="量大可以谈。\n需要多少数量？",
                timestamp="10:32",
            ),
        ],
    )


def test_render_returns_png_bytes():
    png = render_conversation(_sample_conversation(), width=420, phone_style="none")
    assert isinstance(png, bytes)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_image_dimensions_and_opens():
    png = render_conversation(_sample_conversation(), width=500, phone_style="none")
    img = Image.open(BytesIO(png))
    assert img.format == "PNG"
    assert img.width == 500
    assert img.height > 120


def test_render_iphone_frame_adds_bezel():
    png = render_conversation(_sample_conversation(), width=420, phone_style="iphone")
    img = Image.open(BytesIO(png))
    assert img.width > 420  # bezel padding
    assert img.height > 400


def test_render_android_frame_adds_bezel():
    png = render_conversation(_sample_conversation(), width=420, phone_style="android")
    img = Image.open(BytesIO(png))
    assert img.width > 420


def test_render_emoji_message():
    from sales_agent.whatsapp.models import ChatConversation, ChatMessage
    conv = ChatConversation(
        contact_name="Emoji",
        messages=[
            ChatMessage(sender="me", content="Hello 👍 world 🎉"),
            ChatMessage(sender="other", content="你好😀"),
        ],
    )
    png = render_conversation(conv, width=420, phone_style="none")
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_english_word_wrapping():
    # Long word-rich English shouldn't break mid-word when a word fits the bubble.
    from sales_agent.whatsapp.models import ChatConversation, ChatMessage
    conv = ChatConversation(
        contact_name="John",
        messages=[ChatMessage(
            sender="me",
            content="Yes, we've been shipping to Hamburg for 3 years already, no problem.",
            timestamp="10:00",
        )],
    )
    png = render_conversation(conv, width=420, phone_style="none")
    img = Image.open(BytesIO(png))
    assert img.width == 420


def test_render_empty_conversation_still_valid_png():
    conv = ChatConversation(contact_name="Empty", messages=[])
    png = render_conversation(conv, width=420, phone_style="none")
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    img = Image.open(BytesIO(png))
    assert img.width == 420


def test_render_long_message_wraps():
    long = "a" * 500
    conv = ChatConversation(
        contact_name="Long",
        messages=[ChatMessage(sender="me", content=long, timestamp="09:00")],
    )
    png = render_conversation(conv, width=420, phone_style="none")
    img = Image.open(BytesIO(png))
    assert img.height > 200
