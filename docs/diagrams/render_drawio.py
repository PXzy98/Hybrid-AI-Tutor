"""Render a .drawio file to PNG without the draw.io desktop app (Windows, Edge headless).

    python docs\\diagrams\\render_drawio.py docs\\diagrams\\architecture-v3.drawio [--width 1400 --height 1150]

Writes <name>.png next to the .drawio. The page loads draw.io's official viewer script from
viewer.diagrams.net and renders locally in the browser; the diagram itself is not uploaded anywhere.
Edit the diagrams in draw.io (app.diagrams.net or the desktop app); this script only exports them.
"""
import argparse
import html
import json
import subprocess
import tempfile
import time
from pathlib import Path

EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
PAGE = """<!doctype html><html><head><meta charset="utf-8"><style>
html,body{{margin:0;background:#ffffff}} .geDiagramContainer{{overflow:hidden!important}}</style></head><body>
<div class="mxgraph" style="width:{w}px" data-mxgraph="{cfg}"></div>
<script src="https://viewer.diagrams.net/js/viewer-static.min.js"></script></body></html>"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("drawio", type=Path)
    ap.add_argument("--width", type=int, default=1400)
    ap.add_argument("--height", type=int, default=1150)
    a = ap.parse_args()
    xml = a.drawio.read_text("utf-8")
    cfg = json.dumps({"xml": xml, "toolbar": "", "nav": False, "resize": True, "zoom": 1, "border": 10})
    out = a.drawio.with_suffix(".png").resolve()
    page = out.with_suffix(".render.html")
    page.write_text(PAGE.format(w=a.width, cfg=html.escape(cfg, quote=True)), "utf-8")
    profile = tempfile.mkdtemp(prefix="drawio-edge-")  # own profile: never hand off to a running Edge
    started = time.time()
    try:
        subprocess.run([str(EDGE), "--headless", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={profile}",
                        "--force-device-scale-factor=2", f"--window-size={a.width},{a.height}",
                        "--virtual-time-budget=15000", f"--screenshot={out}", page.as_uri()],
                       check=True, capture_output=True)
        # msedge.exe returns before the headless browser has taken the screenshot: wait for the file
        for _ in range(120):
            if out.exists() and out.stat().st_mtime >= started:
                break
            time.sleep(0.5)
        else:
            raise SystemExit("Edge did not write the screenshot within 60 s")
        time.sleep(1)  # let the browser finish writing
    finally:
        page.unlink(missing_ok=True)
    print(f"written {out}")


if __name__ == "__main__":
    main()
