"""English-only source check, including tracked documents and synthetic fixtures."""
import subprocess
import sys
from pathlib import Path


def test_repository_uses_english_only_source_text():
    root = Path(__file__).resolve().parents[2]
    checker = root / "scripts" / "check_english_only.py"
    result = subprocess.run(
        [sys.executable, str(checker)],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
