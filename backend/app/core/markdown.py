"""Markdown images are never shown (web audit S2): the browser would request the image address by itself,
outside the cloud gate, and tell that host the student's IP address. The alt text stays."""

import re

_INLINE = re.compile(r"!\[([^\]\n]*)\]\((?:[^()\n]|\([^()\n]*\))*\)")  # ![alt](url "title")
_REFERENCE = re.compile(r"!\[([^\]\n]*)\](?:\[[^\]\n]*\])?")  # ![alt][ref], ![alt][], ![alt]
_HTML_IMG = re.compile(r"<img\b[^>]*>?", re.IGNORECASE)
_ALT = re.compile(r"""\balt\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.IGNORECASE)

_FENCE = re.compile(r" {0,3}(`{3,}|~{3,})")
_INDENTED = re.compile(r"(?: {4}|\t)")
_LIST_ITEM = re.compile(r" {0,3}(?:[-*+]|\d{1,9}[.)])(?:\s|$)")
_CODE_SPAN = re.compile(r"(?<!`)(`+)(?!`).+?(?<!`)\1(?!`)", re.DOTALL)


def _html_alt(match: re.Match) -> str:
    alt = _ALT.search(match.group(0))
    return (alt.group(1) or alt.group(2) or "") if alt else ""


def _lines(text: str) -> list[tuple[bool, str]]:
    """Each line with whether a Markdown renderer shows it as code: fenced blocks (an unclosed fence runs to
    the end) and indented blocks. An indented line is code only after a blank line or another code line, and
    not inside a list, where it continues the item."""
    out: list[tuple[bool, str]] = []
    fence = ""
    prev_blank, prev_code, in_list = True, False, False
    for line in text.splitlines(keepends=True):
        bare = line.rstrip("\r\n")
        if fence:
            out.append((True, line))
            close = _FENCE.match(bare)
            if close and close.group(1)[0] == fence[0] and len(close.group(1)) >= len(fence) \
                    and not bare[close.end():].strip():
                fence = ""
            continue
        opening = _FENCE.match(bare)
        if opening and not (opening.group(1)[0] == "`" and "`" in bare[opening.end():]):
            fence = opening.group(1)
            out.append((True, line))
            prev_blank, prev_code = False, False
            continue
        blank = not bare.strip()
        indented = _INDENTED.match(bare) is not None
        code = not blank and indented and not in_list and (prev_blank or prev_code)
        if not blank and not indented:
            in_list = _LIST_ITEM.match(bare) is not None
        out.append((code, line))
        prev_blank, prev_code = blank, code
    return out


def _strip_prose(text: str) -> str:
    text = _INLINE.sub(r"\1", text)
    text = _REFERENCE.sub(r"\1", text)
    return _HTML_IMG.sub(_html_alt, text)


def _strip_outside_spans(text: str) -> str:
    parts, last = [], 0
    for span in _CODE_SPAN.finditer(text):
        parts += [_strip_prose(text[last:span.start()]), span.group(0)]
        last = span.end()
    return "".join([*parts, _strip_prose(text[last:])])


def strip_images(text: str) -> str:
    """The text with every Markdown image (inline or reference style) and raw <img> tag replaced by its alt
    text. Code spans and fenced or indented code blocks stay as they are: they are shown as literal text, so
    an image example there requests nothing. A reference definition left behind renders nothing."""
    if not text or ("![" not in text and "<img" not in text.lower()):
        return text
    out: list[str] = []
    prose: list[str] = []
    for code, line in _lines(text):
        if not code:
            prose.append(line)
            continue
        if prose:  # the prose between code blocks is stripped as a whole, so a span over two lines stays one
            out.append(_strip_outside_spans("".join(prose)))
            prose = []
        out.append(line)
    if prose:
        out.append(_strip_outside_spans("".join(prose)))
    return "".join(out)
