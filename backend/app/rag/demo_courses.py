"""Stage a demo course pack (`data/demo_courses/<name>/`) in the layout of IndexedCourseRetriever (task S5).

The pack's `manifest.json` lists course-level documents and modules. Course-level documents go to
`courses/<course_id>/materials/_course/`; each module's note and its bundled reading go to
`courses/<course_id>/materials/<module_id>/`. Module IDs are given by the caller (Z4 creates the modules);
by default they are the modules' order numbers.

Only files inside the repository's `data/` folder are copied; nothing is indexed here (the worker runs
`IndexedCourseRetriever.rebuild` after the privacy scan).
"""
import json
import shutil
from pathlib import Path

DATA_ROOT = Path(__file__).resolve().parents[3] / "data"


class DemoCourseError(ValueError):
    """The demo pack is incomplete or points outside the data folder."""


def _inside(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()) or not resolved.is_file():
        raise DemoCourseError("A file listed in the manifest is missing or outside the pack.")
    return resolved


def stage_demo_course(pack: Path, target_root: Path, course_id: int,
                      module_ids: dict[int, int] | None = None, *, data_root: Path = DATA_ROOT) -> list[Path]:
    """Copy the pack into `target_root/courses/<course_id>/materials/` and return the copied files."""
    if type(course_id) is not int or course_id <= 0:
        raise DemoCourseError("course_id must be a positive integer")
    manifest = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))
    materials = Path(target_root) / "courses" / str(course_id) / "materials"
    copied: list[Path] = []

    def copy(source: Path, folder: str, name: str | None = None) -> None:
        dest = materials / folder / (name or source.name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
        copied.append(dest)

    for relative in manifest["documents"]:
        copy(_inside(pack / relative, pack), "_course")
    for module in manifest["modules"]:
        order = module["module_order"]
        module_id = (module_ids or {}).get(order, order)
        folder = str(module_id)
        copy(_inside(pack / module["demo_note"], pack), folder)
        reading = module.get("bundled_reference")
        if reading:
            copy(_inside(pack / reading, data_root), folder, f"reading_{Path(reading).name}")
    return copied
