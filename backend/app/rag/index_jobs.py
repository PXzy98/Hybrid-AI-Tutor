"""Course material on disk and the index rebuild job (course-structure.md 7; tasks S4 and Z11).

Uploads are scanned with `scan_document()` and the course's privacy profile before anything is stored; a
file whose scan finds student data (`ScanResult.blocking`) is refused and not kept. Accepted files go to
`courses/<course_id>/materials/<module_id | _course>/<name>`, the layout `IndexedCourseRetriever` reads.
Every change enqueues `index.rebuild` (once per course while one is waiting): the worker builds a new
index version with the same scan and publishes it; `current.json` switches retrieval to it at once.
"""
import hashlib
import tempfile
from pathlib import Path

from sqlalchemy import text
from sqlmodel import Session, select

from app.admin.materials import MAX_BYTES, clean_name
from app.platform import jobs
from app.privacy.profiles import privacy_profile, scan_document
from app.rag.course_retriever import IndexedCourseRetriever
from app.rag.documents import DocumentError, extract_text
from app.rag.privacy_adapter import privacy_scan_callback
from app.storage.models import Course, IndexVersion, Job, Material, utcnow

REBUILD = "index.rebuild"


class MaterialRefused(ValueError):
    """The upload is not stored: wrong type, too large, unreadable, or the scan found student data."""


def material_folder(data_root: Path, course_id: int, module_id: int | None) -> Path:
    return Path(data_root) / "courses" / str(course_id) / "materials" / (
        "_course" if module_id is None else str(module_id))


def material_path(data_root: Path, row: Material) -> Path:
    return material_folder(data_root, row.course_id, row.module_id) / row.filename


def check_upload(filename: str, data: bytes, course_type: str) -> str:
    """The cleaned file name; raises MaterialRefused. Only finding types are reported, never text."""
    try:
        name = clean_name(filename)
    except ValueError as e:
        raise MaterialRefused(str(e)) from None
    if not data:
        raise MaterialRefused("the file is empty")
    if len(data) > MAX_BYTES:
        raise MaterialRefused(f"the file is larger than {MAX_BYTES // (1024 * 1024)} MB")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / name
        path.write_bytes(data)
        try:
            text = extract_text(path)
        except DocumentError as e:
            raise MaterialRefused(str(e)) from None
        except Exception:  # noqa: BLE001 - a broken file of an allowed type
            raise MaterialRefused("the file cannot be read") from None
    if not text.strip():
        raise MaterialRefused("no text could be extracted (scanned images are not supported)")
    result = scan_document(text, privacy_profile(course_type))
    if result.blocking:
        raise MaterialRefused("the privacy scan found student data: " + ", ".join(result.blocking))
    return name


def store(engine, data_root: Path, course_id: int, module_id: int | None, name: str, data: bytes) -> Material:
    """Write the accepted file and its row; FileExistsError when the name is taken in that place."""
    folder = material_folder(data_root, course_id, module_id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    with path.open("xb") as stream:  # exclusive: never overwrite another upload
        stream.write(data)
    row = Material(course_id=course_id, module_id=module_id, filename=name, size_bytes=len(data),
                   sha256=hashlib.sha256(data).hexdigest(), scan_status="accepted")
    try:
        with Session(engine, expire_on_commit=False) as db:
            db.add(row)
            db.commit()
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return row


def request_rebuild(engine, course_id: int, account_id: int | None) -> Job:
    """A queued rebuild of the course, or the one already waiting (it will see every file)."""
    with Session(engine, expire_on_commit=False) as db:
        waiting = db.exec(select(Job).where(Job.kind == REBUILD, Job.course_id == course_id,
                                            Job.status == "queued")).first()
    return waiting or jobs.enqueue(engine, REBUILD, course_id=course_id, ref_id=course_id,
                                   created_by=account_id)


def index_version(engine, course_id: int) -> int:
    with Session(engine) as db:
        row = db.get(IndexVersion, course_id)
        return row.version if row else 0


LOCK_NAMESPACE = 7301  # pg_advisory_lock(namespace, course_id): one index build per course at a time


@jobs.handler(REBUILD)
async def rebuild(services, job) -> None:
    """The whole read, build and publish sequence holds a per-course database lock, so two workers never
    build the same course at once: a later build always starts after an earlier one published, and so
    always sees the files as they are now (a deleted file cannot come back)."""
    with Session(services.engine) as db:
        course = db.get(Course, job.course_id)
        course_type = course.course_type
    builder = IndexedCourseRetriever(services.settings.data_path(),
                                     scan=privacy_scan_callback(privacy_profile(course_type)))
    with services.engine.connect() as lock:
        lock.execute(text("SELECT pg_advisory_lock(:n, :c)"), {"n": LOCK_NAMESPACE, "c": job.course_id})
        try:
            version = await builder.rebuild_in_worker(job.course_id)
            with Session(services.engine) as db:
                row = db.get(IndexVersion, job.course_id) or IndexVersion(course_id=job.course_id)
                row.version, row.built_at = version, utcnow()
                db.add(row)
                db.commit()
            builder.prune(job.course_id)
        finally:
            lock.execute(text("SELECT pg_advisory_unlock(:n, :c)"), {"n": LOCK_NAMESPACE, "c": job.course_id})
            lock.commit()
