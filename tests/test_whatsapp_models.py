from sales_agent.whatsapp.models import (
    ChatConversation,
    ChatMessage,
    ScreenshotRequest,
)


def test_chat_message_minimal():
    msg = ChatMessage(sender="me", content="hello")
    assert msg.sender == "me"
    assert msg.content == "hello"
    assert msg.sender_name is None
    assert msg.timestamp is None


def test_chat_conversation_round_trip():
    conv = ChatConversation(
        contact_name="John",
        contact_status="online",
        messages=[
            ChatMessage(sender="other", content="Hi"),
            ChatMessage(sender="me", content="你好", timestamp="10:30"),
        ],
    )
    data = conv.model_dump()
    assert data["contact_name"] == "John"
    assert len(data["messages"]) == 2
    rebuilt = ChatConversation.model_validate(data)
    assert rebuilt == conv


def test_screenshot_request_defaults():
    req = ScreenshotRequest(text="hi")
    assert req.width == 420
    assert req.contact_name is None


def test_screenshot_request_width_bounds():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ScreenshotRequest(text="hi", width=100)
    with pytest.raises(ValidationError):
        ScreenshotRequest(text="hi", width=5000)
