from __future__ import annotations

import re

_NAME_TOKEN = "{name}"

_HONORIFIC_CLEANUP_RE = re.compile(r"(^|\s)님(?=\s|$|[,.!?])")
_MULTI_SPACE_RE = re.compile(r"[ \t]{2,}")
_GARBAGE_NAME_TOKENS = ("undefined", "null", "none", "nil")


def _sanitize_name(name: str | None) -> str:
    if not name:
        return ""
    cleaned = " ".join(name.split()).strip()
    if not cleaned:
        return ""
    parts = [
        part
        for part in cleaned.split(" ")
        if part and part.lower() not in _GARBAGE_NAME_TOKENS
    ]
    return " ".join(parts).strip()


def render_template(template: str, name: str | None) -> str:
    """Replace the literal ``{name}`` token with the provided name.

    Uses a targeted string replace instead of ``str.format`` so user-authored
    brace tokens in templates (e.g. ``{foo}``) do not raise or trigger
    unintended substitutions.

    When ``name`` is empty/None/whitespace-only, the ``{name}`` token is
    dropped and any orphaned ``님`` honorific left behind is trimmed so the
    sentence remains natural.
    """
    if template is None:
        return ""

    if _NAME_TOKEN not in template:
        return template

    cleaned_name = _sanitize_name(name)

    if cleaned_name:
        return template.replace(_NAME_TOKEN, cleaned_name)

    dropped = template.replace(_NAME_TOKEN, "")
    dropped = _HONORIFIC_CLEANUP_RE.sub(r"\1", dropped)
    dropped = _MULTI_SPACE_RE.sub(" ", dropped)
    return dropped.strip()
