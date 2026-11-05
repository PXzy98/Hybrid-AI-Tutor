"""Check that tracked source, fixtures and documents contain no literal CJK text.

Historical multilingual test inputs may be represented with Unicode escape
sequences, preserving runtime semantics without embedding non-English text.
Run from any directory: python scripts/check_english_only.py
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CJK = re.compile(r"[\u3400-\u9fff\uf900-\ufaff\u3000-\u303f\uff00-\uffef]")


def tracked_paths() -> list[Path]:
    output = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
    )
    return [Path(item.decode("utf-8", "surrogateescape"))
            for item in output.split(b"\0") if item]


def find_non_english_text() -> tuple[list[str], int]:
    errors: list[str] = []
    checked = 0
    for relative in tracked_paths():
        path = ROOT / relative
        if not path.is_file():  # staged removals are not active repository files
            continue
        if CJK.search(str(relative)):
            errors.append(f"CJK characters in path: {str(relative)!a}")
        raw = path.read_bytes()
        if b"\0" in raw:
            continue
        try:
            content = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            continue
        checked += 1
        matches = [(i, line) for i, line in enumerate(content.splitlines(), 1)
                   if CJK.search(line)]
        for line_no, line in matches[:4]:
            errors.append(f"{str(relative)!a}:{line_no}: {line[:120]!a}")
        if len(matches) > 4:
            errors.append(f"{str(relative)!a}: ... {len(matches) - 4} more lines")
    return errors, checked


def main() -> int:
    problems, checked = find_non_english_text()
    if problems:
        print("English-only repository check FAILED:")
        print("\n".join(problems))
        return 1
    print(f"English-only repository check passed: {checked} text files inspected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
