"""Builds docs/diagrams/privacy-filter.drawio (editable) and privacy-filter.svg from one layout spec.

    .venv\\Scripts\\python docs\\diagrams\\make_privacy_filter.py
    python docs\\diagrams\\render_drawio.py docs\\diagrams\\privacy-filter.drawio --width 1520 --height 1260
"""
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
W, H = 1500, 1200
BOUNDARY_W = 1080  # privacy boundary: x from 30 to 30 + BOUNDARY_W

# palette shared with architecture-v3 (green = privacy/learner, white = core, red = cloud, orange = local model)
STYLE = {
    "in": ("#e3edf9", "#2b6cc4"), "step": ("#e6f4ee", "#1f9e6e"), "core": ("#ffffff", "#5b6472"),
    "dec": ("#fff6d8", "#c9930a"), "cloud": ("#fbe5e5", "#d64545"), "local": ("#fdebe1", "#e06a2c"),
    "store": ("#f1f1ef", "#6b6b6b"), "stop": ("#fbe5e5", "#d64545"),
}

# id: (x, y, w, h, kind, title, body)
NODES = {
    "q": (60, 70, 300, 80, "in", "Student question (raw text)", "POST /api/v1/ask · student_id from the login session"),
    "id": (60, 190, 300, 90, "step", "Load identity terms",
           "display name, its parts (≥ 3 letters), username · read from `account`, kept in memory only"),
    "det": (440, 60, 600, 230, "step", "1 · Detect (all recognizers run on the same text)",
            "spaCy NER (en_core_web_lg) → PERSON\nPresidio patterns → EMAIL_ADDRESS, PHONE_NUMBER\n"
            "custom: STUDENT_ID (9 digits; spaced only with context words) · GRADE (“I got 58/100”, “my GPA…”)\n"
            "custom: PHONE (North American, separators required) · Chinese self-introduction names\n"
            "custom: HEALTH_DETAIL — condition / symptom / medicine / reading of the student or someone they know\n"
            "custom: POSTAL_CODE · HEALTH_CARD · ID_NUMBER (SIN, MRN) · DATE_OF_BIRTH · ADDRESS · French phrasing\n"
            "identity terms → PERSON / USERNAME (whole words, always)"),
    "clean": (440, 330, 600, 130, "step", "2 · Clean up",
              "drop scores < 0.5 · person fixes: cut digits, drop acronyms, drop eponyms (Cohen's kappa)\n"
              "allow-list: course staff (Dr. Abbas) · overlaps: a PERSON span never hides a health detail;\n"
              "otherwise keep the longer span, then the higher score"),
    "anon": (440, 500, 600, 100, "step", "3 · Anonymize",
             "replace each finding by a numbered placeholder <PERSON_1>, <STUDENT_ID_1>, …\n"
             "placeholder → value mapping: private attribute of the request, memory only"),
    "dec": (560, 640, 360, 90, "dec", "4 · Personal health detail?", "HEALTH_DETAIL found → cloud_safe = false"),
    "err": (60, 320, 320, 110, "stop", "Filter unavailable / error",
            "missing spaCy model or exception → request stops (HTTP 503) · never skipped"),
    "store": (60, 490, 320, 120, "store", "Stored and logged",
              "sanitized text only: request_log, session history, admin logs · never the raw question"),
    "route": (440, 780, 280, 90, "core", "Router (Tongkai, semantic)",
              "capability + evidence → local or cloud · no privacy branch"),
    "local": (60, 780, 320, 110, "local", "Local model (inside the boundary)",
              "may see the raw question and the full learner context"),
    "guard": (770, 780, 310, 130, "step", "5 · Cloud gate (every router)",
              "cloud_safe = false: local_only → local · generalize → checked hypothetical rewrite\n"
              "leak guard: PII, student_id, item IDs, misconception text → block\n"
              "no / failing cloud model → local"),
    "cloud": (1170, 780, 300, 120, "cloud", "Cloud LLM (outside)",
              "CloudRequest only: sanitized question, topic, passages, 3 coarse labels"),
    "restore": (440, 950, 600, 90, "step", "6 · Restore + verify",
                "placeholders → original values in the answer · pii_leak / profile_leak checkers · mapping cleared"),
    "ans": (1170, 955, 300, 80, "in", "Answer to the student", "with sources and a check question"),
}
EDGES = [
    ("q", "id", ""), ("q", "det", "raw text"), ("id", "det", "terms"), ("det", "clean", "findings"),
    ("clean", "anon", ""), ("anon", "dec", ""), ("det", "err", "error"), ("anon", "store", "sanitized text"),
    ("dec", "route", "sanitized text + flag"), ("route", "local", "local"), ("route", "guard", "cloud"),
    ("guard", "cloud", "pass"), ("local", "restore", "answer"),
    ("cloud", "restore", "answer"), ("restore", "ans", ""),
]


def center(n):
    x, y, w, h = NODES[n][:4]
    return x + w / 2, y + h / 2


def anchor(a, b):
    """Point on a's border towards b's centre."""
    x, y, w, h = NODES[a][:4]
    cx, cy = center(a)
    tx, ty = center(b)
    dx, dy = tx - cx, ty - cy
    if dx == dy == 0:
        return cx, cy
    sx = (w / 2) / abs(dx) if dx else float("inf")
    sy = (h / 2) / abs(dy) if dy else float("inf")
    s = min(sx, sy)
    return cx + dx * s, cy + dy * s


def wrap(text: str, width: float, px: float = 6.2) -> list[str]:
    """Greedy word wrap by an estimated character width."""
    limit, out = max(10, int(width / px)), []
    for para in text.split("\n"):
        line = ""
        for word in para.split(" "):
            if line and len(line) + 1 + len(word) > limit:
                out.append(line)
                line = word
            else:
                line = f"{line} {word}".strip()
        out.append(line)
    return out


# guard -> local when blocked: drawn under the route box, with waypoints
BLOCKED = [(925, 910), (925, 932), (220, 932), (220, 890)]


def svg() -> str:
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" font-family="Arial, sans-serif">',
           '<defs><marker id="arr" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto">'
           '<path d="M0,0 L10,4 L0,8 z" fill="#5b6472"/></marker></defs>',
           f'<rect width="{W}" height="{H}" fill="white"/>',
           '<text x="30" y="36" font-size="22" font-weight="bold">Privacy filter · detailed flow (subfunctions and links)</text>',
           f'<rect x="30" y="50" width="{BOUNDARY_W}" height="1010" fill="none" stroke="#d64545" stroke-dasharray="8,6"/>',
           '<text x="1170" y="760" font-size="13" fill="#d64545">outside the boundary</text>',
           '<text x="40" y="1085" font-size="13" fill="#d64545">Red dashed line = privacy boundary (application '
           'server + local GPU server). Only the CloudRequest crosses it; the raw question and the placeholder '
           'mapping never leave it.</text>',
           '<polyline points="' + " ".join(f"{x},{y}" for x, y in BLOCKED) + '" fill="none" stroke="#5b6472" '
           'stroke-width="1.6" stroke-dasharray="5,4" marker-end="url(#arr)"/>',
           '<rect x="440" y="924" width="270" height="16" fill="white"/><text x="575" y="936" font-size="11" '
           'text-anchor="middle" fill="#334155">kept local / blocked / no cloud → local + notice</text>']
    for a, b, label in EDGES:
        x1, y1 = anchor(a, b)
        x2, y2 = anchor(b, a)
        out.append(f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" stroke="#5b6472" '
                   f'stroke-width="1.6" marker-end="url(#arr)"/>')
        if label:
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            out.append(f'<rect x="{mx - len(label) * 3.3:.0f}" y="{my - 10:.0f}" width="{len(label) * 6.6:.0f}" '
                       f'height="16" fill="white"/><text x="{mx:.0f}" y="{my + 2:.0f}" font-size="11" '
                       f'text-anchor="middle" fill="#334155">{escape(label)}</text>')
    for n, (x, y, w, h, kind, title, body) in NODES.items():
        fill, stroke = STYLE[kind]
        shape = (f'<polygon points="{x + w / 2},{y} {x + w},{y + h / 2} {x + w / 2},{y + h} {x},{y + h / 2}" '
                 if kind == "dec" else f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" ')
        out.append(shape + f'fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
        lines = wrap(body, w - (w * 0.45 if kind == "dec" else 24))
        ty = y + (h - 18 - 15 * len(lines)) / 2 + 16
        out.append(f'<text x="{x + w / 2}" y="{ty:.0f}" font-size="14" font-weight="bold" '
                   f'text-anchor="middle">{escape(title)}</text>')
        for i, line in enumerate(lines):
            out.append(f'<text x="{x + w / 2}" y="{ty + 18 + i * 15:.0f}" font-size="11.5" fill="#475569" '
                       f'text-anchor="middle">{escape(line)}</text>')
    legend = [("step", "privacy subfunction (ours)"), ("core", "pipeline step"), ("dec", "decision"),
              ("local", "local model"), ("cloud", "cloud"), ("store", "storage")]
    for i, (k, t) in enumerate(legend):
        fill, stroke = STYLE[k]
        out.append(f'<rect x="{40 + i * 235}" y="1120" width="16" height="16" fill="{fill}" stroke="{stroke}"/>'
                   f'<text x="{62 + i * 235}" y="1133" font-size="12">{t}</text>')
    out.append("</svg>")
    return "\n".join(out)


def drawio() -> str:
    def text(cid, x, y, w, h, value, style):
        return (f'<mxCell id="{cid}" value="{escape(value)}" style="text;html=1;align=left;verticalAlign=middle;'
                f'{style}" vertex="1" parent="1"><mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" '
                f'as="geometry"/></mxCell>')

    cells = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>',
             f'<mxCell id="boundary" value="" style="rounded=0;html=1;fillColor=none;strokeColor=#d64545;dashed=1;'
             f'dashPattern=8 6;strokeWidth=1.5;" vertex="1" parent="1"><mxGeometry x="30" y="50" '
             f'width="{BOUNDARY_W}" height="1010" as="geometry"/></mxCell>',
             text("title", 30, 14, 900, 30, "<b>Privacy filter · detailed flow (subfunctions and links)</b>",
                  "fontSize=22;"),
             text("outside", 1170, 750, 200, 20, "outside the boundary", "fontSize=13;fontColor=#d64545;"),
             text("note", 40, 1072, 1400, 24, "Red dashed line = privacy boundary (application server + local GPU "
                  "server). Only the CloudRequest crosses it; the raw question and the placeholder mapping never "
                  "leave it.", "fontSize=13;fontColor=#d64545;")]
    for n, (x, y, w, h, kind, title, body) in NODES.items():
        fill, stroke = STYLE[kind]
        shape = "rhombus;" if kind == "dec" else "rounded=1;arcSize=8;"
        value = escape(f"<b>{escape(title)}</b><br><font style='font-size:10px' color='#475569'>"
                       f"{escape(body).replace(chr(10), '<br>')}</font>")
        cells.append(f'<mxCell id="{n}" value="{value}" style="{shape}whiteSpace=wrap;html=1;fillColor={fill};'
                     f'strokeColor={stroke};strokeWidth=2;fontSize=12;" vertex="1" parent="1">'
                     f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')
    for i, (a, b, label) in enumerate(EDGES):
        cells.append(f'<mxCell id="e{i}" value="{escape(label)}" style="endArrow=block;html=1;strokeColor=#5b6472;'
                     f'fontSize=10;" edge="1" parent="1" source="{a}" target="{b}">'
                     f'<mxGeometry relative="1" as="geometry"/></mxCell>')
    points = "".join(f'<mxPoint x="{x}" y="{y}"/>' for x, y in BLOCKED[1:-1])
    cells.append('<mxCell id="blocked" value="kept local / blocked / no cloud → local + notice" '
                 'style="endArrow=block;html=1;strokeColor=#5b6472;dashed=1;dashPattern=5 4;fontSize=10;'
                 'exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=1;entryDx=0;entryDy=0;'
                 'labelBackgroundColor=#ffffff;" edge="1" parent="1" source="guard" target="local">'
                 f'<mxGeometry relative="1" as="geometry"><Array as="points">{points}</Array></mxGeometry></mxCell>')
    return (f'<mxfile host="app.diagrams.net" type="device"><diagram id="privacy-filter" name="privacy-filter">'
            f'<mxGraphModel dx="1200" dy="900" grid="1" gridSize="10" page="1" pageWidth="{W}" pageHeight="{H}">'
            f'<root>{"".join(cells)}</root></mxGraphModel></diagram></mxfile>')


(HERE / "privacy-filter.svg").write_text(svg(), encoding="utf-8")
(HERE / "privacy-filter.drawio").write_text(drawio(), encoding="utf-8")
print("written privacy-filter.svg and privacy-filter.drawio")
