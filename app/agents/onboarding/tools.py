"""Small text-parsing helpers for onboarding answers. Kept dumb/deterministic on purpose —
these don't need an LLM call, which keeps onboarding fast and cheap."""
import re
from datetime import time

from app.agents.onboarding.prompts import SKIP_ALL_KEYWORDS, SKIP_KEYWORDS


def is_skip(text: str) -> bool:
    return text.strip().lower() in SKIP_KEYWORDS


def is_skip_all(text: str) -> bool:
    return text.strip().lower() in SKIP_ALL_KEYWORDS


def split_list_answer(text: str) -> list[str]:
    """'Tesla, Nvidia and the semiconductor sector' -> ['Tesla', 'Nvidia', 'the semiconductor sector']"""
    parts = re.split(r",|\band\b|/|\n", text, flags=re.IGNORECASE)
    return [p.strip() for p in parts if p.strip()]


def parse_time_answer(text: str) -> time | None:
    text = text.strip().lower().replace(" ", "")
    # 24h "HH:MM"
    m = re.match(r"^(\d{1,2}):(\d{2})$", text)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        if 0 <= h < 24 and 0 <= mi < 60:
            return time(h, mi)
    # "8am" / "9:30pm"
    m = re.match(r"^(\d{1,2})(:(\d{2}))?(am|pm)$", text)
    if m:
        h = int(m.group(1)) % 12
        mi = int(m.group(3)) if m.group(3) else 0
        if m.group(4) == "pm":
            h += 12
        return time(h, mi)
    return None
