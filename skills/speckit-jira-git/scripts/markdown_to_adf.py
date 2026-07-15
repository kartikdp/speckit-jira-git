"""Tiny markdown-to-ADF converter.

Handles the subset of markdown the skill produces internally: paragraphs,
ATX headings (## H2, ### H3, ...), bullet lists with `-` or `*`, and inline
code marked with backticks. Anything fancier (tables, links, blockquotes,
nested lists) is rendered as plain text inside a paragraph; readers should
prefer keeping comment bodies simple so the output stays clean.

This is intentionally hand-rolled to avoid adding a markdown library to the
dependency surface.
"""
from __future__ import annotations

import re
from typing import Iterator


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_BULLET_RE = re.compile(r"^[-*]\s+(.+)$")
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")


def _text_run(text: str) -> list[dict]:
    """Convert a single line into ADF text nodes, splitting at backtick spans
    so inline code renders with the `code` mark."""
    nodes: list[dict] = []
    last = 0
    for m in _INLINE_CODE_RE.finditer(text):
        if m.start() > last:
            plain = text[last : m.start()]
            if plain:
                nodes.append({"type": "text", "text": plain})
        nodes.append(
            {"type": "text", "text": m.group(1), "marks": [{"type": "code"}]}
        )
        last = m.end()
    tail = text[last:]
    if tail:
        nodes.append({"type": "text", "text": tail})
    return nodes or [{"type": "text", "text": text}]


def _paragraph(text: str) -> dict:
    return {"type": "paragraph", "content": _text_run(text)}


def _heading(level: int, text: str) -> dict:
    level = max(1, min(level, 6))
    return {
        "type": "heading",
        "attrs": {"level": level},
        "content": _text_run(text),
    }


def _bullet_list(lines: list[str]) -> dict:
    return {
        "type": "bulletList",
        "content": [
            {"type": "listItem", "content": [_paragraph(line)]} for line in lines
        ],
    }


def markdown_to_adf(md: str) -> dict:
    """Convert a markdown string to a top-level ADF doc."""
    blocks: list[dict] = []
    paragraph_buf: list[str] = []
    bullet_buf: list[str] = []

    def flush_paragraph() -> None:
        if paragraph_buf:
            text = " ".join(paragraph_buf).strip()
            if text:
                blocks.append(_paragraph(text))
            paragraph_buf.clear()

    def flush_bullets() -> None:
        if bullet_buf:
            blocks.append(_bullet_list(bullet_buf[:]))
            bullet_buf.clear()

    for raw_line in md.splitlines():
        line = raw_line.rstrip()

        if not line.strip():
            flush_paragraph()
            flush_bullets()
            continue

        m = _HEADING_RE.match(line)
        if m:
            flush_paragraph()
            flush_bullets()
            blocks.append(_heading(len(m.group(1)), m.group(2)))
            continue

        m = _BULLET_RE.match(line)
        if m:
            flush_paragraph()
            bullet_buf.append(m.group(1))
            continue

        # Plain text line. If a bullet block was open, close it.
        flush_bullets()
        paragraph_buf.append(line)

    flush_paragraph()
    flush_bullets()

    if not blocks:
        blocks = [_paragraph("")]

    return {"type": "doc", "version": 1, "content": blocks}


def adf_to_summary_text(adf: dict, limit: int = 80) -> str:
    """Return a flat one-line summary of an ADF doc, useful for previews."""

    def walk(node) -> Iterator[str]:
        if isinstance(node, dict):
            if node.get("type") == "text" and isinstance(node.get("text"), str):
                yield node["text"]
            for v in node.values():
                yield from walk(v)
        elif isinstance(node, list):
            for item in node:
                yield from walk(item)

    flat = " ".join(walk(adf)).strip()
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "…"
