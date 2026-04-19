from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from sales_agent.config import settings
from sales_agent.whatsapp.models import ChatConversation, ChatMessage

logger = logging.getLogger(__name__)

BG_COLOR = "#efeae2"
HEADER_COLOR = "#008069"
HEADER_TEXT_COLOR = "#ffffff"
HEADER_STATUS_COLOR = "#d9fdd3"
ME_BUBBLE_COLOR = "#d9fdd3"
OTHER_BUBBLE_COLOR = "#ffffff"
BUBBLE_TEXT_COLOR = "#111b21"
TIMESTAMP_COLOR = "#667781"
TICK_COLOR = "#53bdeb"
SENDER_NAME_COLOR = "#1f7a8c"
AVATAR_BG_COLOR = "#cfd8dc"
AVATAR_TEXT_COLOR = "#ffffff"

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/System/Library/Fonts/PingFang.ttc",
    "C:\\Windows\\Fonts\\msyh.ttc",
]


@dataclass
class Fonts:
    body: ImageFont.ImageFont
    header: ImageFont.ImageFont
    status: ImageFont.ImageFont
    meta: ImageFont.ImageFont
    sender: ImageFont.ImageFont


def _load_font_file() -> str | None:
    candidates = []
    if settings.whatsapp_font_path:
        candidates.append(settings.whatsapp_font_path)
    candidates.extend(FONT_CANDIDATES)
    for path in candidates:
        if path and Path(path).exists():
            return path
    logger.warning("未找到可用的中文字体，将退化为 Pillow 默认字体（可能无法显示中文）")
    return None


def _load_fonts() -> Fonts:
    path = _load_font_file()
    if path is None:
        default = ImageFont.load_default()
        return Fonts(body=default, header=default, status=default, meta=default, sender=default)
    return Fonts(
        body=ImageFont.truetype(path, 15),
        header=ImageFont.truetype(path, 17),
        status=ImageFont.truetype(path, 11),
        meta=ImageFont.truetype(path, 10),
        sender=ImageFont.truetype(path, 12),
    )


def _wrap_text(text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    """Greedy per-character wrap suitable for mixed CJK/latin."""
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
            continue
        current = ""
        i = 0
        while i < len(paragraph):
            ch = paragraph[i]
            trial = current + ch
            width = font.getlength(trial) if hasattr(font, "getlength") else font.getbbox(trial)[2]
            if width <= max_width or not current:
                current = trial
                i += 1
            else:
                lines.append(current)
                current = ""
        if current:
            lines.append(current)
    return lines


def _text_height(font: ImageFont.ImageFont) -> int:
    bbox = font.getbbox("Ay你好")
    return bbox[3] - bbox[1]


def _measure_line(font: ImageFont.ImageFont, text: str) -> int:
    if hasattr(font, "getlength"):
        return int(font.getlength(text))
    bbox = font.getbbox(text)
    return bbox[2] - bbox[0]


@dataclass
class _LaidOutMessage:
    message: ChatMessage
    lines: list[str]
    bubble_width: int
    bubble_height: int
    show_sender_name: bool
    line_height: int


def _lay_out(
    messages: list[ChatMessage],
    fonts: Fonts,
    max_bubble_width: int,
    padding_x: int,
    padding_y: int,
) -> list[_LaidOutMessage]:
    laid_out: list[_LaidOutMessage] = []
    prev_sender: str | None = None
    prev_sender_name: str | None = None
    text_inner_width = max_bubble_width - 2 * padding_x
    line_height = _text_height(fonts.body) + 4
    meta_height = _text_height(fonts.meta)
    sender_height = _text_height(fonts.sender) + 2

    for msg in messages:
        lines = _wrap_text(msg.content, fonts.body, text_inner_width)
        if not lines:
            lines = [""]
        longest = max(_measure_line(fonts.body, ln) for ln in lines)
        meta_text = msg.timestamp or ""
        meta_width = _measure_line(fonts.meta, meta_text) + (14 if msg.sender == "me" else 0)
        content_width = max(longest, meta_width)
        bubble_width = min(content_width + 2 * padding_x, max_bubble_width)

        show_sender_name = bool(
            msg.sender_name
            and msg.sender == "other"
            and (msg.sender != prev_sender or msg.sender_name != prev_sender_name)
        )

        bubble_height = padding_y * 2 + len(lines) * line_height + meta_height + 4
        if show_sender_name:
            bubble_height += sender_height
            if msg.sender_name:
                sender_w = _measure_line(fonts.sender, msg.sender_name) + 2 * padding_x
                bubble_width = min(max(bubble_width, sender_w), max_bubble_width)

        laid_out.append(
            _LaidOutMessage(
                message=msg,
                lines=lines,
                bubble_width=bubble_width,
                bubble_height=bubble_height,
                show_sender_name=show_sender_name,
                line_height=line_height,
            )
        )
        prev_sender = msg.sender
        prev_sender_name = msg.sender_name

    return laid_out


def _draw_header(
    draw: ImageDraw.ImageDraw,
    img: Image.Image,
    conv: ChatConversation,
    fonts: Fonts,
    width: int,
    height: int,
) -> None:
    draw.rectangle([(0, 0), (width, height)], fill=HEADER_COLOR)
    avatar_r = 18
    cx, cy = 48, height // 2
    draw.ellipse(
        [(cx - avatar_r, cy - avatar_r), (cx + avatar_r, cy + avatar_r)],
        fill=AVATAR_BG_COLOR,
    )
    initial = (conv.contact_name.strip() or "?")[0].upper()
    init_w = _measure_line(fonts.header, initial)
    init_h = _text_height(fonts.header)
    draw.text(
        (cx - init_w / 2, cy - init_h / 2 - 2),
        initial,
        fill=AVATAR_TEXT_COLOR,
        font=fonts.header,
    )
    name_x = cx + avatar_r + 10
    draw.text((name_x, 10), conv.contact_name, fill=HEADER_TEXT_COLOR, font=fonts.header)
    if conv.contact_status:
        draw.text(
            (name_x, 10 + _text_height(fonts.header) + 4),
            conv.contact_status,
            fill=HEADER_STATUS_COLOR,
            font=fonts.status,
        )


def _draw_tick(draw: ImageDraw.ImageDraw, x: int, y: int, color: str) -> None:
    draw.line([(x, y + 4), (x + 3, y + 7), (x + 9, y + 1)], fill=color, width=1)
    draw.line([(x + 4, y + 4), (x + 7, y + 7), (x + 13, y + 1)], fill=color, width=1)


def _draw_bubble(
    draw: ImageDraw.ImageDraw,
    laid: _LaidOutMessage,
    top: int,
    width: int,
    fonts: Fonts,
    margin: int,
    padding_x: int,
    padding_y: int,
) -> None:
    msg = laid.message
    is_me = msg.sender == "me"
    bubble_color = ME_BUBBLE_COLOR if is_me else OTHER_BUBBLE_COLOR

    if is_me:
        right = width - margin
        left = right - laid.bubble_width
    else:
        left = margin
        right = left + laid.bubble_width
    bottom = top + laid.bubble_height

    draw.rounded_rectangle(
        [(left, top), (right, bottom)],
        radius=8,
        fill=bubble_color,
    )
    # little tail pointer
    if is_me:
        tail = [(right, top), (right + 6, top), (right, top + 8)]
    else:
        tail = [(left, top), (left - 6, top), (left, top + 8)]
    draw.polygon(tail, fill=bubble_color)

    text_y = top + padding_y
    if laid.show_sender_name and msg.sender_name:
        draw.text(
            (left + padding_x, text_y),
            msg.sender_name,
            fill=SENDER_NAME_COLOR,
            font=fonts.sender,
        )
        text_y += _text_height(fonts.sender) + 2

    for line in laid.lines:
        draw.text(
            (left + padding_x, text_y),
            line,
            fill=BUBBLE_TEXT_COLOR,
            font=fonts.body,
        )
        text_y += laid.line_height

    # Timestamp + ticks, bottom-right of bubble
    meta_text = msg.timestamp or ""
    meta_w = _measure_line(fonts.meta, meta_text)
    meta_x = right - padding_x - meta_w - (14 if is_me else 0)
    meta_y = bottom - padding_y - _text_height(fonts.meta) + 1
    if meta_text:
        draw.text((meta_x, meta_y), meta_text, fill=TIMESTAMP_COLOR, font=fonts.meta)
    if is_me:
        _draw_tick(draw, right - padding_x - 12, meta_y, TICK_COLOR)


def render_conversation(conv: ChatConversation, width: int = 420) -> bytes:
    """Render a conversation as a WhatsApp-style PNG (light theme). Returns PNG bytes."""
    fonts = _load_fonts()

    margin = 10
    padding_x = 9
    padding_y = 6
    max_bubble_width = int(width * 0.75)

    laid_messages = _lay_out(
        conv.messages, fonts, max_bubble_width, padding_x, padding_y
    )

    header_height = 60
    gap_same = 4
    gap_diff = 10
    total_body_height = 12  # top padding inside chat area
    prev_sender: str | None = None
    for laid in laid_messages:
        if prev_sender is None:
            pass
        elif laid.message.sender == prev_sender:
            total_body_height += gap_same
        else:
            total_body_height += gap_diff
        total_body_height += laid.bubble_height
        prev_sender = laid.message.sender
    total_body_height += 14  # bottom padding
    total_body_height = max(total_body_height, 120)

    height = header_height + total_body_height
    img = Image.new("RGB", (width, height), BG_COLOR)
    draw = ImageDraw.Draw(img)
    _draw_header(draw, img, conv, fonts, width, header_height)

    y = header_height + 12
    prev_sender = None
    for laid in laid_messages:
        if prev_sender is None:
            pass
        elif laid.message.sender == prev_sender:
            y += gap_same
        else:
            y += gap_diff
        _draw_bubble(draw, laid, y, width, fonts, margin, padding_x, padding_y)
        y += laid.bubble_height
        prev_sender = laid.message.sender

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
