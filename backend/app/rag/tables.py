"""Markdown tables as one passage per row, each carrying its column names.

A course calendar is a table (`| LEC # | TOPICS | KEY DATES |`). Chunked as plain lines, a row such as
`| 12 | Midterm | |` says nothing about what the cells mean and cannot be matched by "which session is the
midterm". Here every data row becomes "Lecture 12. TOPICS: Midterm" under the heading of its section.
Tables are recognised in the text itself; some sources put a blank line between rows and have no
`|---|` separator row, so both forms work.
"""
import re

_HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*#*$")
_SEPARATOR_CELL = re.compile(r":?-{2,}:?")
_COUNTER = re.compile(r"[A-Za-z]{0,3}\d+[A-Za-z]?")
_ABBREVIATIONS = {"lec": "Lecture", "ses": "Session", "rec": "Recitation", "no": "Number"}
MAX_ROW_CHARS = 650


def _cells(line: str) -> list[str] | None:
    """The cells of a Markdown table row, or None when the line is not one."""
    line = line.strip()
    if not (line.startswith("|") and line.endswith("|")) or line.count("|") < 3:
        return None
    return [" ".join(cell.split()) for cell in line[1:-1].split("|")]


def _is_separator(cells: list[str]) -> bool:
    return all(_SEPARATOR_CELL.fullmatch(c) for c in cells if c) and any(cells)


def _label(header: str) -> str:
    """A column name with the common abbreviations of course calendars spelled out ("LEC #" -> "Lecture")."""
    words = [w for w in header.replace("#", " ").split() if w]
    return " ".join(_ABBREVIATIONS.get(w.lower().rstrip("."), w) for w in words)


def _row_parts(headers: list[str], values: list[str]) -> list[str]:
    parts = []
    for position, (header, value) in enumerate(zip(headers, values, strict=False)):
        if not value or set(value) <= {"-", " "}:
            continue
        label = _label(header)
        if position == 0 and label and _COUNTER.fullmatch(value):
            parts.append(f"{label} {value}")  # "Lecture 12", "Week 3"
        elif label:
            parts.append(f"{label}: {value}")
        else:
            parts.append(value)
    return parts


def _row_passages(parts: list[str]) -> list[str]:
    """One passage per row; a row longer than MAX_ROW_CHARS is split by cell, repeating its first cell."""
    out, current = [], []
    for part in parts:
        if current and len(". ".join([*current, part])) > MAX_ROW_CHARS:
            out.append(". ".join(current))
            current = [parts[0]]
        current.append(part)
    if current:
        out.append(". ".join(current))
    return out


def split_tables(body: str) -> tuple[str, list[tuple[str, str]]]:
    """Return (the text without its table rows, [(heading, row passage), ...]).

    The heading is the last Markdown heading before the table ("Overview" without one). A table of one row
    and a table without any data row stay in the text.
    """
    lines = body.splitlines()
    kept: list[str] = []
    rows: list[tuple[str, str]] = []
    heading = "Overview"
    i = 0
    while i < len(lines):
        match = _HEADING.match(lines[i].strip())
        if match:
            heading = match.group(1)
        if _cells(lines[i]) is None:
            kept.append(lines[i])
            i += 1
            continue
        # One table: table lines, blank lines between them allowed.
        start, table, j = i, [], i
        while j < len(lines):
            cells = _cells(lines[j])
            if cells is not None:
                table.append(cells)
            elif lines[j].strip():
                break
            j += 1
        # Do not swallow the blank lines after the last row.
        end = j
        while end > start and not lines[end - 1].strip():
            end -= 1
        separator = next((n for n, cells in enumerate(table) if n and _is_separator(cells)), None)
        header_at = 0 if separator is None else separator - 1
        data = [c for n, c in enumerate(table) if n > header_at and n != separator]
        if not data:
            kept.extend(lines[start:end])
        else:
            headers = table[header_at]
            for values in data:
                rows.extend((heading, text) for text in _row_passages(_row_parts(headers, values)))
        i = max(end, start + 1)
    return "\n".join(kept), rows
