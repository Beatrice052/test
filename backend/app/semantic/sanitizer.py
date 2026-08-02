"""Sanitize untrusted semantic metadata before it reaches retrieval or prompts."""

import html
import re
import unicodedata
from typing import NamedTuple

from app.contracts.common import Sha256, semantic_hash

CONTROL_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
ZERO_WIDTH_PATTERN = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060\ufeff]")
HTML_TAG_PATTERN = re.compile(r"<[^>]{1,500}>")
CODE_FENCE_PATTERN = re.compile(r"```.*?```", flags=re.DOTALL)
INSTRUCTION_PATTERN = re.compile(
    r"(?i)(ignore\s+(all\s+)?previous|system\s+prompt|developer\s+message|"
    r"执行.{0,12}(删除|命令)|忽略.{0,12}(规则|指令)|delete\s+index)"
)


class SanitizedText(NamedTuple):
    text: str
    original_hash: Sha256
    events: tuple[str, ...]


class DescriptionSanitizer:
    def __init__(self, *, max_length: int = 2000) -> None:
        self.max_length = max_length

    def sanitize(self, value: str) -> SanitizedText:
        original_hash = semantic_hash(value)
        text = unicodedata.normalize("NFKC", html.unescape(value))
        events: list[str] = []

        text, count = CONTROL_PATTERN.subn(" ", text)
        if count:
            events.append("CONTROL_CHAR_REMOVED")
        text, count = ZERO_WIDTH_PATTERN.subn("", text)
        if count:
            events.append("ZERO_WIDTH_REMOVED")
        text, count = HTML_TAG_PATTERN.subn(" ", text)
        if count:
            events.append("HTML_REMOVED")
        text, count = CODE_FENCE_PATTERN.subn(" [code removed] ", text)
        if count:
            events.append("CODE_FENCE_REMOVED")
        text, count = INSTRUCTION_PATTERN.subn("[untrusted instruction removed]", text)
        if count:
            events.append("INSTRUCTION_PATTERN_REMOVED")

        text = re.sub(r"\s+", " ", text).strip()
        if len(text) > self.max_length:
            text = text[: self.max_length].rstrip()
            events.append("TRUNCATED")
        if not text:
            text = "[sanitized empty description]"
            events.append("EMPTY_AFTER_SANITIZE")
        return SanitizedText(text=text, original_hash=original_hash, events=tuple(events))
