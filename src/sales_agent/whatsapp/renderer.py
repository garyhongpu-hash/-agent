from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from PIL import Image, ImageDraw, ImageFont

from sales_agent.config import settings
from sales_agent.whatsapp.emoji_support import (
    EmojiRenderer,
    Token,
    load_emoji_font,
    tokenize,
)
from sales_agent.whatsapp.models import ChatConversation, ChatMessage

logger = logging.getLogger(__name__)

PhoneStyle = Literal["iphone", "android", "none"]

# Chat palette (WhatsApp light theme, modern)
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
INPUT_BG = "#ffffff"
INPUT_BORDER = "#e5e7eb"
SYSTEM_BEZEL_COLOR = "#0a0a0a"
STATUS_BAR_ICON_COLOR = "#ffffff"

# Text font search order (body + header); CJK-capable first.
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/System/Library/Fonts/PingFang.ttc",
    "C:\\Windows\\Fonts\\msyh.ttc",
]


@dataclass
class Fonts:
    body: ImageFont.ImageFont
    body_size: int
    header: ImageFont.ImageFont
    status: ImageFont.ImageFont
    meta: ImageFont.ImageFont
    sender: ImageFont.ImageFont
    status_bar: ImageFont.ImageFont


def _load_font_file() -> str | None:
    candidates: list[str] = []
    if settings.whatsapp_font_path:
        candidates.append(settings.whatsapp_font_path)
    candidates.extend(FONT_CANDIDATES)
    for path in candidates:
        if path and Path(path).exists():
            return path
    logger.warning("未找到可用的中文字体，将退化为 Pillow 默认字体")
    return None


def _load_fonts() -> Fonts:
    path = _load_font_file()
    if path is None:
        d = ImageFont.load_default()
        return Fonts(body=d, body_size=11, header=d, status=d, meta=d, sender=d, status_bar=d)
    body_size = 15
    return Fonts(
        body=ImageFont.truetype(path, body_size),
        body_size=body_size,
        header=ImageFont.truetype(path, 17),
        status=ImageFont.truetype(path, 11),
        meta=ImageFont.truetype(path, 10),
        sender=ImageFont.truetype(path, 12),
        status_bar=ImageFont.truetype(path, 13),
    )


# ---------------------------------------------------------------------------
# Token measurement & word-aware wrapping
# ---------------------------------------------------------------------------


def _measure_text(font: ImageFont.ImageFont, text: str) -> int:
    if hasattr(font, "getlength"):
        return int(font.getlength(text))
    bbox = font.getbbox(text)
    return bbox[2] - bbox[0]


def _token_width(tok: Token, font: ImageFont.ImageFont, emoji_size: int) -> int:
    if tok.type == "emoji":
        return emoji_size + 1  # small trailing gap
    if tok.type == "newline":
        return 0
    return _measure_text(font, tok.text)


def _break_long_word(tok: Token, font: ImageFont.ImageFont, max_width: int) -> list[Token]:
    """Break a too-long word token into char tokens so it can fit."""
    out: list[Token] = []
    for ch in tok.text:
        out.append(Token("word", ch))
    return out


def wrap_tokens(
    tokens: list[Token],
    font: ImageFont.ImageFont,
    emoji_size: int,
    max_width: int,
) -> list[list[Token]]:
    """Word-aware wrapping for mixed CJK/latin/emoji.

    - Latin "word" tokens stay contiguous (wrap on whitespace boundary).
    - CJK and emoji tokens can break anywhere.
    - If a word by itself exceeds max_width, it is split per character.
    """
    lines: list[list[Token]] = [[]]
    cur_w = 0
    for tok in tokens:
        if tok.type == "newline":
            lines.append([])
            cur_w = 0
            continue
        tw = _token_width(tok, font, emoji_size)
        if tok.type == "space" and cur_w == 0:
            continue  # drop leading spaces
        if cur_w == 0 or cur_w + tw <= max_width:
            lines[-1].append(tok)
            cur_w += tw
            continue
        # Overflow: strip trailing spaces on current line, start new line
        while lines[-1] and lines[-1][-1].type == "space":
            popped = lines[-1].pop()
            cur_w -= _token_width(popped, font, emoji_size)
        lines.append([])
        cur_w = 0
        if tok.type == "space":
            continue
        if tok.type == "word" and tw > max_width:
            for sub in _break_long_word(tok, font, max_width):
                sw = _token_width(sub, font, emoji_size)
                if cur_w + sw > max_width and cur_w > 0:
                    lines.append([])
                    cur_w = 0
                lines[-1].append(sub)
                cur_w += sw
        else:
            lines[-1].append(tok)
            cur_w = tw
    return lines


def _line_width(line: list[Token], font: ImageFont.ImageFont, emoji_size: int) -> int:
    return sum(_token_width(tok, font, emoji_size) for tok in line)


def _text_height(font: ImageFont.ImageFont) -> int:
    bbox = font.getbbox("Ay你好")
    return bbox[3] - bbox[1]


# ---------------------------------------------------------------------------
# Layout + drawing primitives
# ---------------------------------------------------------------------------


@dataclass
class _LaidOutMessage:
    message: ChatMessage
    lines: list[list[Token]]
    line_height: int
    bubble_width: int
    bubble_height: int
    show_sender_name: bool


def _lay_out(
    messages: list[ChatMessage],
    fonts: Fonts,
    emoji_size: int,
    max_bubble_width: int,
    padding_x: int,
    padding_y: int,
) -> list[_LaidOutMessage]:
    laid_out: list[_LaidOutMessage] = []
    prev_sender: str | None = None
    prev_sender_name: str | None = None
    line_height = max(emoji_size, _text_height(fonts.body)) + 5
    meta_height = _text_height(fonts.meta)
    sender_height = _text_height(fonts.sender) + 2
    text_inner_width = max_bubble_width - 2 * padding_x

    for msg in messages:
        tokens = tokenize(msg.content)
        lines = wrap_tokens(tokens, fonts.body, emoji_size, text_inner_width)
        if not lines:
            lines = [[]]
        longest = max(_line_width(ln, fonts.body, emoji_size) for ln in lines)
        meta_text = msg.timestamp or ""
        meta_width = _measure_text(fonts.meta, meta_text) + (14 if msg.sender == "me" else 0)
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
                sn_w = _measure_text(fonts.sender, msg.sender_name) + 2 * padding_x
                bubble_width = min(max(bubble_width, sn_w), max_bubble_width)

        laid_out.append(
            _LaidOutMessage(
                message=msg,
                lines=lines,
                line_height=line_height,
                bubble_width=bubble_width,
                bubble_height=bubble_height,
                show_sender_name=show_sender_name,
            )
        )
        prev_sender = msg.sender
        prev_sender_name = msg.sender_name

    return laid_out


def _draw_line(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    line: list[Token],
    font: ImageFont.ImageFont,
    body_size: int,
    emoji_renderer: EmojiRenderer,
    fill: str,
) -> None:
    cursor = x
    baseline_y = y + (max(body_size, emoji_renderer_target(body_size)) - _text_height(font)) // 2
    emoji_target = emoji_renderer_target(body_size)
    text_top = y
    for tok in line:
        if tok.type == "emoji":
            em = emoji_renderer.render(tok.text, emoji_target)
            if em is None:
                draw.text((cursor, text_top), "□", font=font, fill=fill)
                cursor += _measure_text(font, "□") + 1
            else:
                paste_y = text_top + (_text_height(font) - em.height) // 2
                if paste_y < y:
                    paste_y = y
                img.paste(em, (cursor, paste_y), em)
                cursor += em.width + 1
        elif tok.type == "newline":
            continue
        else:
            draw.text((cursor, text_top), tok.text, font=font, fill=fill)
            cursor += _measure_text(font, tok.text)


def emoji_renderer_target(body_size: int) -> int:
    return int(body_size * 1.1)


def _draw_tick(draw: ImageDraw.ImageDraw, x: int, y: int, color: str) -> None:
    draw.line([(x, y + 4), (x + 3, y + 7), (x + 9, y + 1)], fill=color, width=1)
    draw.line([(x + 4, y + 4), (x + 7, y + 7), (x + 13, y + 1)], fill=color, width=1)


def _draw_bubble(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    laid: _LaidOutMessage,
    top: int,
    chat_left: int,
    chat_right: int,
    fonts: Fonts,
    emoji_renderer: EmojiRenderer,
    margin: int,
    padding_x: int,
    padding_y: int,
) -> None:
    msg = laid.message
    is_me = msg.sender == "me"
    bubble_color = ME_BUBBLE_COLOR if is_me else OTHER_BUBBLE_COLOR

    if is_me:
        right = chat_right - margin
        left = right - laid.bubble_width
    else:
        left = chat_left + margin
        right = left + laid.bubble_width
    bottom = top + laid.bubble_height

    draw.rounded_rectangle([(left, top), (right, bottom)], radius=8, fill=bubble_color)
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
        _draw_line(
            img,
            draw,
            left + padding_x,
            text_y,
            line,
            fonts.body,
            fonts.body_size,
            emoji_renderer,
            BUBBLE_TEXT_COLOR,
        )
        text_y += laid.line_height

    meta_text = msg.timestamp or ""
    meta_w = _measure_text(fonts.meta, meta_text)
    meta_x = right - padding_x - meta_w - (14 if is_me else 0)
    meta_y = bottom - padding_y - _text_height(fonts.meta) + 1
    if meta_text:
        draw.text((meta_x, meta_y), meta_text, fill=TIMESTAMP_COLOR, font=fonts.meta)
    if is_me:
        _draw_tick(draw, right - padding_x - 12, meta_y, TICK_COLOR)


def _draw_chat_header(
    draw: ImageDraw.ImageDraw,
    conv: ChatConversation,
    fonts: Fonts,
    left: int,
    top: int,
    right: int,
    bottom: int,
) -> None:
    draw.rectangle([(left, top), (right, bottom)], fill=HEADER_COLOR)
    # Back chevron
    chev_x = left + 12
    cy = (top + bottom) // 2
    draw.line([(chev_x + 6, cy - 6), (chev_x, cy), (chev_x + 6, cy + 6)],
              fill=HEADER_TEXT_COLOR, width=2)
    # Avatar
    avatar_r = 16
    ax = chev_x + 10 + avatar_r
    draw.ellipse([(ax - avatar_r, cy - avatar_r), (ax + avatar_r, cy + avatar_r)],
                 fill=AVATAR_BG_COLOR)
    initial = (conv.contact_name.strip() or "?")[0].upper()
    iw = _measure_text(fonts.header, initial)
    ih = _text_height(fonts.header)
    draw.text((ax - iw / 2, cy - ih / 2 - 2), initial, fill=AVATAR_TEXT_COLOR, font=fonts.header)
    # Name + status
    name_x = ax + avatar_r + 8
    name_h = _text_height(fonts.header)
    status_h = _text_height(fonts.status)
    total_h = name_h + (4 + status_h if conv.contact_status else 0)
    name_y = cy - total_h // 2 - 2
    draw.text((name_x, name_y), conv.contact_name, fill=HEADER_TEXT_COLOR, font=fonts.header)
    if conv.contact_status:
        draw.text(
            (name_x, name_y + name_h + 4),
            conv.contact_status,
            fill=HEADER_STATUS_COLOR,
            font=fonts.status,
        )
    # Right-side icons: video + call + overflow (3 small circles placeholder)
    icon_y = cy
    for i, _name in enumerate(("video", "call", "more")):
        ix = right - 20 - i * 28
        if _name == "more":
            for dot in range(3):
                draw.ellipse(
                    [(ix + 1, icon_y - 7 + dot * 5), (ix + 5, icon_y - 3 + dot * 5)],
                    fill=HEADER_TEXT_COLOR,
                )
        elif _name == "call":
            draw.arc([(ix - 2, icon_y - 8), (ix + 14, icon_y + 8)], 135, 45,
                     fill=HEADER_TEXT_COLOR, width=2)
        else:  # video
            draw.rounded_rectangle([(ix - 8, icon_y - 5), (ix + 4, icon_y + 5)],
                                   radius=2, fill=HEADER_TEXT_COLOR)
            draw.polygon([(ix + 4, icon_y - 3), (ix + 10, icon_y - 6),
                          (ix + 10, icon_y + 6), (ix + 4, icon_y + 3)],
                         fill=HEADER_TEXT_COLOR)


def _draw_input_bar(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    fonts: Fonts,
    left: int,
    top: int,
    right: int,
    bottom: int,
) -> None:
    draw.rectangle([(left, top), (right, bottom)], fill=BG_COLOR)
    pill_left = left + 10
    pill_right = right - 50
    pill_top = top + 6
    pill_bottom = bottom - 6
    draw.rounded_rectangle(
        [(pill_left, pill_top), (pill_right, pill_bottom)],
        radius=18, fill=INPUT_BG, outline=INPUT_BORDER, width=1,
    )
    # Mic / send button (green circle)
    btn_r = (pill_bottom - pill_top) // 2
    bx = right - 10 - btn_r
    by = (pill_top + pill_bottom) // 2
    draw.ellipse([(bx - btn_r, by - btn_r), (bx + btn_r, by + btn_r)], fill=HEADER_COLOR)
    # mic rectangle
    draw.rounded_rectangle(
        [(bx - 3, by - 5), (bx + 3, by + 2)], radius=3, fill="#ffffff",
    )
    draw.arc([(bx - 5, by - 2), (bx + 5, by + 6)], 0, 180, fill="#ffffff", width=2)
    draw.line([(bx, by + 5), (bx, by + 7)], fill="#ffffff", width=2)


# ---------------------------------------------------------------------------
# Phone frame
# ---------------------------------------------------------------------------


@dataclass
class PhoneChrome:
    style: PhoneStyle
    bezel: int = 0
    outer_radius: int = 0
    screen_radius: int = 0
    status_bar_height: int = 0
    footer_height: int = 0  # home indicator area / nav bar
    notch_width: int = 0
    notch_height: int = 0
    camera_hole_radius: int = 0
    mock_time: str = "9:41"

    @classmethod
    def for_style(cls, style: PhoneStyle) -> PhoneChrome:
        if style == "iphone":
            return cls(
                style="iphone",
                bezel=12,
                outer_radius=52,
                screen_radius=40,
                status_bar_height=44,
                footer_height=28,
                notch_width=110,
                notch_height=30,
            )
        if style == "android":
            return cls(
                style="android",
                bezel=10,
                outer_radius=36,
                screen_radius=26,
                status_bar_height=30,
                footer_height=40,
                camera_hole_radius=8,
            )
        return cls(style="none")


def _draw_ios_status_bar(
    draw: ImageDraw.ImageDraw, fonts: Fonts, chrome: PhoneChrome,
    x: int, y: int, width: int,
) -> None:
    # Green (WhatsApp) background already drawn. Add notch.
    height = chrome.status_bar_height
    cy = y + height // 2
    # Dynamic Island
    nx0 = x + (width - chrome.notch_width) // 2
    nx1 = nx0 + chrome.notch_width
    ny0 = y + 8
    ny1 = ny0 + chrome.notch_height
    draw.rounded_rectangle([(nx0, ny0), (nx1, ny1)], radius=chrome.notch_height // 2, fill="#000000")
    # Time (left)
    time_text = chrome.mock_time
    tw = _measure_text(fonts.status_bar, time_text)
    draw.text(
        (x + 22, cy - _text_height(fonts.status_bar) // 2 - 1),
        time_text,
        fill=STATUS_BAR_ICON_COLOR,
        font=fonts.status_bar,
    )
    # Icons (right): signal bars, wifi, battery
    _draw_status_icons(draw, x + width - 80, cy, width=68, color=STATUS_BAR_ICON_COLOR)


def _draw_android_status_bar(
    draw: ImageDraw.ImageDraw, fonts: Fonts, chrome: PhoneChrome,
    x: int, y: int, width: int,
) -> None:
    cy = y + chrome.status_bar_height // 2
    draw.text(
        (x + 14, cy - _text_height(fonts.status_bar) // 2 - 1),
        chrome.mock_time,
        fill=STATUS_BAR_ICON_COLOR,
        font=fonts.status_bar,
    )
    # Camera hole at top center
    r = chrome.camera_hole_radius
    cx = x + width // 2
    hole_cy = y + chrome.status_bar_height // 2
    draw.ellipse([(cx - r, hole_cy - r), (cx + r, hole_cy + r)], fill="#000000")
    _draw_status_icons(draw, x + width - 70, cy, width=60, color=STATUS_BAR_ICON_COLOR)


def _draw_status_icons(draw: ImageDraw.ImageDraw, x: int, cy: int, width: int, color: str) -> None:
    # Signal: 4 bars
    bx = x
    for i in range(4):
        h = 3 + i * 2
        draw.rectangle([(bx + i * 4, cy + 5 - h), (bx + i * 4 + 3, cy + 5)], fill=color)
    # Wifi: three arcs
    wx = bx + 22
    for i in range(3):
        r = 7 - i * 2
        draw.arc([(wx - r, cy - r), (wx + r, cy + r)], 220, 320, fill=color, width=2)
    draw.ellipse([(wx - 1, cy + 4), (wx + 1, cy + 6)], fill=color)
    # Battery
    bx2 = x + width - 26
    draw.rounded_rectangle([(bx2, cy - 5), (bx2 + 22, cy + 5)], radius=2, outline=color, width=1)
    draw.rectangle([(bx2 + 22, cy - 2), (bx2 + 24, cy + 2)], fill=color)
    draw.rounded_rectangle([(bx2 + 2, cy - 3), (bx2 + 18, cy + 3)], radius=1, fill=color)


def _draw_iphone_footer(
    draw: ImageDraw.ImageDraw, chrome: PhoneChrome, x: int, y: int, width: int,
) -> None:
    bar_w = 134
    bar_h = 5
    bx = x + (width - bar_w) // 2
    by = y + (chrome.footer_height - bar_h) // 2 + 6
    draw.rounded_rectangle([(bx, by), (bx + bar_w, by + bar_h)], radius=bar_h // 2, fill="#ffffff")


def _draw_android_footer(
    draw: ImageDraw.ImageDraw, chrome: PhoneChrome, x: int, y: int, width: int,
) -> None:
    cy = y + chrome.footer_height // 2
    cx = x + width // 2
    color = "#ffffff"
    # Back triangle
    draw.polygon(
        [(cx - 60 - 8, cy), (cx - 60 + 6, cy - 8), (cx - 60 + 6, cy + 8)],
        fill=color,
    )
    # Home circle
    draw.ellipse([(cx - 9, cy - 9), (cx + 9, cy + 9)], outline=color, width=2)
    # Recent square
    draw.rectangle([(cx + 52, cy - 8), (cx + 68, cy + 8)], outline=color, width=2)


# ---------------------------------------------------------------------------
# Public: render_conversation
# ---------------------------------------------------------------------------


def render_conversation(
    conv: ChatConversation,
    width: int = 420,
    phone_style: PhoneStyle = "iphone",
) -> bytes:
    """Render a WhatsApp-style chat screenshot as PNG.

    ``width`` is the chat content width in pixels. When ``phone_style`` is
    ``iphone`` or ``android``, a phone bezel + status bar + home indicator is
    drawn around the chat area, producing a full-phone mockup.
    """
    fonts = _load_fonts()
    emoji_font = load_emoji_font()
    emoji_renderer = EmojiRenderer(emoji_font)
    emoji_size = emoji_renderer_target(fonts.body_size)

    chrome = PhoneChrome.for_style(phone_style)

    margin = 10
    padding_x = 9
    padding_y = 6
    max_bubble_width = int(width * 0.76)

    laid_messages = _lay_out(
        conv.messages, fonts, emoji_size, max_bubble_width, padding_x, padding_y
    )

    chat_header_height = 56
    input_bar_height = 44
    gap_same = 4
    gap_diff = 10
    body_height = 12
    prev_sender: str | None = None
    for laid in laid_messages:
        if prev_sender is None:
            pass
        elif laid.message.sender == prev_sender:
            body_height += gap_same
        else:
            body_height += gap_diff
        body_height += laid.bubble_height
        prev_sender = laid.message.sender
    body_height += 12
    body_height = max(body_height, 120)

    chat_total_height = (
        chrome.status_bar_height
        + chat_header_height
        + body_height
        + input_bar_height
        + chrome.footer_height
    )
    img_width = width + 2 * chrome.bezel
    img_height = chat_total_height + 2 * chrome.bezel

    img = Image.new("RGB", (img_width, img_height), "#ffffff")
    draw = ImageDraw.Draw(img)

    # Outer bezel (rounded black)
    if chrome.bezel > 0:
        draw.rounded_rectangle(
            [(0, 0), (img_width - 1, img_height - 1)],
            radius=chrome.outer_radius,
            fill=SYSTEM_BEZEL_COLOR,
        )

    # Inner screen with rounded clip. We build the screen on an RGBA layer then
    # composite through a rounded mask.
    screen_x = chrome.bezel
    screen_y = chrome.bezel
    screen_w = width
    screen_h = chat_total_height
    screen_layer = Image.new("RGB", (screen_w, screen_h), BG_COLOR)
    slayer_draw = ImageDraw.Draw(screen_layer)

    # Status bar (filled green like WA header for seamless look)
    slayer_draw.rectangle(
        [(0, 0), (screen_w, chrome.status_bar_height)], fill=HEADER_COLOR
    )
    if chrome.style == "iphone":
        _draw_ios_status_bar(slayer_draw, fonts, chrome, 0, 0, screen_w)
    elif chrome.style == "android":
        _draw_android_status_bar(slayer_draw, fonts, chrome, 0, 0, screen_w)

    # Chat header directly below status bar
    header_top = chrome.status_bar_height
    header_bottom = header_top + chat_header_height
    _draw_chat_header(slayer_draw, conv, fonts, 0, header_top, screen_w, header_bottom)

    # Chat body
    y = header_bottom + 12
    prev_sender = None
    for laid in laid_messages:
        if prev_sender is None:
            pass
        elif laid.message.sender == prev_sender:
            y += gap_same
        else:
            y += gap_diff
        _draw_bubble(
            screen_layer, slayer_draw, laid,
            top=y, chat_left=0, chat_right=screen_w,
            fonts=fonts, emoji_renderer=emoji_renderer,
            margin=margin, padding_x=padding_x, padding_y=padding_y,
        )
        y += laid.bubble_height
        prev_sender = laid.message.sender

    # Input bar
    input_top = chrome.status_bar_height + chat_header_height + body_height
    input_bottom = input_top + input_bar_height
    _draw_input_bar(screen_layer, slayer_draw, fonts, 0, input_top, screen_w, input_bottom)

    # Footer (home indicator / nav bar) over black background
    footer_top = input_bottom
    if chrome.footer_height > 0:
        slayer_draw.rectangle(
            [(0, footer_top), (screen_w, footer_top + chrome.footer_height)],
            fill="#000000",
        )
        if chrome.style == "iphone":
            _draw_iphone_footer(slayer_draw, chrome, 0, footer_top, screen_w)
        elif chrome.style == "android":
            _draw_android_footer(slayer_draw, chrome, 0, footer_top, screen_w)

    # Round the screen corners by masking
    if chrome.screen_radius > 0:
        mask = Image.new("L", (screen_w, screen_h), 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            [(0, 0), (screen_w - 1, screen_h - 1)],
            radius=chrome.screen_radius,
            fill=255,
        )
        img.paste(screen_layer, (screen_x, screen_y), mask)
    else:
        img.paste(screen_layer, (screen_x, screen_y))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
