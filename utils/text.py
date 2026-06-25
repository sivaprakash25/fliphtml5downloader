"""Text utility helpers."""

from __future__ import annotations


def sanitize_filename(value: str | None) -> str:
    if not value:
        return "book"
    safe = []
    for ch in value:
        if ch.isalnum() or ch in (" ", "-", "_", "."):
            safe.append(ch)
        else:
            safe.append("_")
    name = "".join(safe).strip().replace(" ", "_")
    return name or "book"


def clean_description(value: str | None, max_len: int | None = None) -> str:
    if not value:
        return ""
    desc = value.replace("\n", " ")
    desc = " ".join(desc.split())
    if max_len is not None and len(desc) > max_len:
        desc = desc[: max_len - 3].rstrip() + "..."
    return desc


def short_label(value: str | None, max_len: int = 36) -> str:
    if not value:
        return "-"
    if len(value) <= max_len:
        return value
    if max_len < 10:
        return value[:max_len]
    head = max_len // 2 - 2
    tail = max_len - head - 3
    return value[:head] + "..." + value[-tail:]
