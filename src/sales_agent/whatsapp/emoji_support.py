from __future__ import annotations

import logging
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import emoji as emoji_lib
from PIL import Image, ImageFont

logger = logging.getLogger(__name__)

EMOJI_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
    "/System/Library/Fonts/Apple Color Emoji.ttc",
    "C:\\Windows\\Fonts\\seguiemj.ttf",
]

# Noto Color Emoji ships glyphs as 109px embedded bitmaps; loading at 109 is safest.
EMOJI_NATIVE_SIZE = 109

TokenType = Literal["word", "cjk", "emoji", "space", "newline"]


@dataclass
class Token:
    type: TokenType
    text: str


def _is_cjk(ch: str) -> bool:
    code = ord(ch)
    # Common CJK ranges + fullwidth punctuation
    return (
        0x3000 <= code <= 0x303F  # CJK Symbols and Punctuation
        or 0x3040 <= code <= 0x30FF  # Hiragana + Katakana
        or 0x3400 <= code <= 0x4DBF  # CJK Ext A
        or 0x4E00 <= code <= 0x9FFF  # CJK Unified
        or 0xAC00 <= code <= 0xD7AF  # Hangul
        or 0xF900 <= code <= 0xFAFF  # CJK Compat
        or 0xFE30 <= code <= 0xFE4F  # CJK Compat forms
        or 0xFF00 <= code <= 0xFFEF  # Halfwidth + Fullwidth
    )


def tokenize(text: str) -> list[Token]:
    """Split text into word/cjk/emoji/space/newline tokens.

    Emoji sequences (including ZWJ multi-codepoint emoji like 👨‍👩‍👧) are
    detected via the ``emoji`` library. Latin words are kept contiguous so the
    wrapper can break on word boundaries. CJK runs are split per character.
    """
    emoji_spans = emoji_lib.emoji_list(text)
    emoji_at: dict[int, tuple[int, str]] = {
        span["match_start"]: (span["match_end"], span["emoji"])
        for span in emoji_spans
    }

    tokens: list[Token] = []
    i = 0
    n = len(text)
    word_buf: list[str] = []

    def flush_word() -> None:
        if word_buf:
            tokens.append(Token("word", "".join(word_buf)))
            word_buf.clear()

    while i < n:
        if i in emoji_at:
            flush_word()
            end, e = emoji_at[i]
            tokens.append(Token("emoji", e))
            i = end
            continue
        ch = text[i]
        if ch == "\n":
            flush_word()
            tokens.append(Token("newline", "\n"))
            i += 1
        elif ch == " " or ch == "\t":
            flush_word()
            run = ch
            i += 1
            while i < n and text[i] in (" ", "\t"):
                run += text[i]
                i += 1
            tokens.append(Token("space", run))
        elif _is_cjk(ch):
            flush_word()
            tokens.append(Token("cjk", ch))
            i += 1
        else:
            # punctuation directly joins adjacent word char if any
            word_buf.append(ch)
            i += 1

    flush_word()
    return tokens


def load_emoji_font(path: str | None = None) -> ImageFont.ImageFont | None:
    """Load Noto/Apple Color Emoji font, or return None if unavailable."""
    candidates: list[str] = []
    if path:
        candidates.append(path)
    candidates.extend(EMOJI_FONT_CANDIDATES)
    for p in candidates:
        if p and Path(p).exists():
            try:
                return ImageFont.truetype(p, EMOJI_NATIVE_SIZE)
            except OSError:
                continue
    logger.warning("未找到彩色 emoji 字体，emoji 会被替换为占位符")
    return None


class EmojiRenderer:
    """Rasterize emoji glyphs at native size then cache scaled versions."""

    def __init__(self, font: ImageFont.ImageFont | None):
        self.font = font
        self._cache: dict[tuple[str, int], Image.Image] = {}

    @property
    def available(self) -> bool:
        return self.font is not None

    def render(self, ch: str, target_size: int) -> Image.Image | None:
        if self.font is None:
            return None
        key = (ch, target_size)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        canvas = Image.new("RGBA", (EMOJI_NATIVE_SIZE + 10, EMOJI_NATIVE_SIZE + 10), (0, 0, 0, 0))
        try:
            from PIL import ImageDraw

            ImageDraw.Draw(canvas).text(
                (0, 0), ch, font=self.font, embedded_color=True
            )
        except Exception:
            return None
        bbox = canvas.getbbox()
        if bbox is None:
            return None
        cropped = canvas.crop(bbox)
        # scale longest side to target_size
        longest = max(cropped.size)
        scale = target_size / longest
        new_w = max(1, round(cropped.width * scale))
        new_h = max(1, round(cropped.height * scale))
        resized = cropped.resize((new_w, new_h), Image.LANCZOS)
        self._cache[key] = resized
        return resized
