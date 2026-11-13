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


def _split(inner: str) -> list[str]:
    """Split a row on unescaped pipes outside backtick code spans; a backslash before a pipe keeps it."""
    cells, current, code, i = [], [], False, 0
    while i < len(inner):
        ch = inner[i]
        if ch == "\\" and i + 1 < len(inner) and inner[i + 1] == "|":
            current.append("|")
            i += 2
            continue
        if ch == "`":
            code = not code
        if ch == "|" and not code:
            cells.append("".join(current))
            current = []
        else:
            current.append(ch)
        i += 1
    cells.append("".join(current))
    return cells


def _cells(line: str) -> list[str] | None:
    """The cells of a Markdown table row, or None when the line is not one."""
    line = line.strip()
    if not (line.startswith("|") and line.endswith("|")) or len(line) < 3:
        return None
    cells = _split(line[1:-1])
    if len(cells) < 2:
        return None
    return [" ".join(cell.split()) for cell in cells]


def _is_separator(cells: list[str]) -> bool:
    return all(_SEPARATOR_CELL.fullmatch(c) for c in cells if c) and any(cells)


def _label(header: str) -> str:
    """A column name with the common abbreviations of course calendars spelled out ("LEC #" -> "Lecture")."""
    words = [w for w in header.replace("#", " ").split() if w]
    return " ".join(_ABBREVIATIONS.get(w.lower().rstrip("."), w) for w in words)


def _row_parts(headers: list[str], values: list[str]) -> list[str]:
    parts = []
    if headers and len(values) > len(headers):  # never drop a cell: the extra ones join the last column
        values = [*values[:len(headers) - 1], " | ".join(v for v in values[len(headers) - 1:] if v)]
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
        emitted = False
        headers: list[str] | None = None
        n = 0
        while n < len(table):
            row = table[n]
            if n + 1 < len(table) and _is_separator(table[n + 1]) and not _is_separator(row):
                headers, n = row, n + 2  # a header row and its separator start a (new) table
            elif _is_separator(row):
                n += 1
            elif headers is None:
                headers, n = row, n + 1  # no separator row: the first row names the columns
            else:
                for text in _row_passages(_row_parts(headers, row)):
                    rows.append((heading, text))
                    emitted = True
                n += 1
        if not emitted:
            kept.extend(lines[start:end])
        i = max(end, start + 1)
    return "\n".join(kept), rows
