"""Start next term's course from this one (V17 finding W12; course-structure.md 3.5).

Copies what an instructor builds: the course settings and guideline, the modules with their guidelines, the
KCs, check items and misconceptions (the content export and import of `CatalogEditor`, so there is one
copier), the quizzes as drafts and the materials with their module. It copies nothing about people: no
members except the caller, no learner state, request logs, conversations, quiz attempts or survey answers,
no invitation code, and no connection of the source course (its API key stays with that course).
"""
import shutil
from dataclasses import dataclass

from sqlmodel import Session, select

from app.catalog.editor import CatalogEditor
from app.platform.courses import CourseService, CourseView
from app.platform.settings import COURSE_FIELDS, SettingsService
from app.rag import index_jobs
from app.storage.models import AuditLog, Course, Material, ModelEndpoint, Module, Quiz


@dataclass
class NextTermResult:
    course: CourseView
    copied: dict[str, int]
    rebuild_job_id: int | None


def copy_course(engine, courses: CourseService, settings: SettingsService, editor: CatalogEditor, data_root,
                source_id: int, account_id: int, *, code: str, title: str, term_label: str,
                max_import_bytes: int) -> NextTermResult:
    with Session(engine) as db:
        source = db.get(Course, source_id)
        modules = db.exec(select(Module).where(Module.course_id == source_id)).all()
        guideline = source.guideline
        source_type = source.course_type
        module_codes = {m.id: m.code for m in modules}
    # the course-creation rules (enabled type, unique code) apply as for a new course
    new = courses.create(account_id, code=code, title=title, course_type=source_type, term_label=term_label)
    try:
        copied = _copy_into(engine, settings, editor, data_root, source_id, new.id, account_id, guideline,
                            module_codes, max_import_bytes)
    except Exception:
        with Session(engine) as db:
            row = db.get(Course, new.id)
            if row is not None:
                db.delete(row)  # the database cascades to everything copied so far
                db.commit()
        shutil.rmtree(index_jobs.material_folder(data_root, new.id, None).parent.parent, ignore_errors=True)
        raise
    job_id = None
    if copied["materials"]:
        job_id = index_jobs.request_rebuild(engine, new.id, account_id).id
    with Session(engine) as db:
        db.add(AuditLog(account_id=account_id, action="course.copy", target=f"course:{new.id}",
                        details={"source_course_id": source_id, **copied}))
        db.commit()
    return NextTermResult(courses.get(new.id, my_role="instructor"), copied, job_id)


def _copy_into(engine, settings, editor, data_root, source_id, new_id, account_id, guideline, module_codes,
               max_import_bytes) -> dict[str, int]:
    copied = {"modules": 0, "kcs": 0, "items": 0, "misconceptions": 0, "quizzes": 0, "materials": 0}
    _copy_settings(engine, settings, source_id, new_id, account_id)
    if module_codes:
        counts = editor.import_zip(new_id, editor.export_zip(source_id), max_bytes=max_import_bytes)
        copied.update(counts.__dict__)
    with Session(engine) as db:
        db.get(Course, new_id).guideline = guideline
        new_modules = {m.code: m.id for m in db.exec(select(Module).where(Module.course_id == new_id)).all()}
        mapping = {old: new_modules[code] for old, code in module_codes.items() if code in new_modules}
        for q in db.exec(select(Quiz).where(Quiz.course_id == source_id).order_by(Quiz.id)).all():
            db.add(Quiz(course_id=new_id, module_id=mapping.get(q.module_id), title=q.title, kind=q.kind,
                        status="draft", questions=[dict(x) for x in q.questions], created_by=account_id))
            copied["quizzes"] += 1
        rows = db.exec(select(Material).where(Material.course_id == source_id).order_by(Material.id)).all()
        for m in rows:
            module_id = mapping.get(m.module_id) if m.module_id is not None else None
            if m.module_id is not None and module_id is None:
                continue
            src = index_jobs.material_path(data_root, m)
            if not src.is_file():
                continue
            dst = index_jobs.material_folder(data_root, new_id, module_id) / m.filename
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
            db.add(Material(course_id=new_id, module_id=module_id, filename=m.filename,
                            size_bytes=m.size_bytes, sha256=m.sha256, scan_status=m.scan_status))
            copied["materials"] += 1
        db.commit()
    return copied


def _copy_settings(engine, settings: SettingsService, source_id, new_id, account_id) -> None:
    values, _ = settings.course_values(source_id)
    with Session(engine) as db:
        for name in ("local_endpoint_id", "cloud_endpoint_id"):
            endpoint = db.get(ModelEndpoint, values[name]) if values.get(name) else None
            if endpoint is not None and endpoint.course_id is not None:
                values[name] = None  # a connection of the source course (and its key) is not copied
    if any(values[f] is not None for f in COURSE_FIELDS):
        settings.save_course(new_id, values, expected_version=0, account_id=account_id,
                             action="settings.course.copy")
