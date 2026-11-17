"""Markdown images are never shown (web audit S2): the browser would request the image address by itself,
outside the cloud gate, and tell that host the student's IP address. The alt text stays."""

import re

_INLINE = re.compile(r"!\[([^\]\n]*)\]\((?:[^()\n]|\([^()\n]*\))*\)")  # ![alt](url "title")
_REFERENCE = re.compile(r"!\[([^\]\n]*)\](?:\[[^\]\n]*\])?")  # ![alt][ref], ![alt][], ![alt]
_HTML_IMG = re.compile(r"<img\b[^>]*>?", re.IGNORECASE)
_ALT = re.compile(r"""\balt\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.IGNORECASE)


def _html_alt(match: re.Match) -> str:
    alt = _ALT.search(match.group(0))
    return (alt.group(1) or alt.group(2) or "") if alt else ""


def strip_images(text: str) -> str:
    """The text with every Markdown image (inline or reference style) and raw <img> tag replaced by its alt
    text. A reference definition left behind renders nothing."""
    if not text or ("![" not in text and "<img" not in text.lower()):
        return text
    text = _INLINE.sub(r"\1", text)
    text = _REFERENCE.sub(r"\1", text)
    return _HTML_IMG.sub(_html_alt, text)
