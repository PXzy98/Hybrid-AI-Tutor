"""Write the OpenAPI schema for the frontend type generator.

    python -m app.export_openapi            # -> frontend/openapi.json
"""
import json
import sys
from pathlib import Path

from app.core.config import REPO_ROOT
from app.main import create_app


def main(out: Path = REPO_ROOT / "frontend" / "openapi.json") -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(create_app().openapi(), indent=2) + "\n", encoding="utf-8")
    return out


if __name__ == "__main__":
    print(main(Path(sys.argv[1])) if len(sys.argv) > 1 else main())
