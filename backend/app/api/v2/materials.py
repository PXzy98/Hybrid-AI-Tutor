"""Course material (api-v2.md 3.4; course-structure.md 7): upload, list, delete. Each upload is scanned
before it is stored (`app.rag.index_jobs`); a change starts an index rebuild job (`GET .../jobs/{id}`)."""
import asyncio
import hashlib
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile, status
from pydantic import BaseModel, Field
from sqlmodel import Session, col, select

from app.admin.materials import MAX_BYTES
from app.api.v2.errors import ApiError, ErrorCode
from app.platform.access import CourseAccess, require_course_role
from app.rag import index_jobs, web_pages
from app.storage.models import AuditLog, Material, Module, utcnow

router = APIRouter(tags=["materials"])
CourseInstructor = Annotated[CourseAccess, Depends(require_course_role("instructor"))]


class MaterialOut(BaseModel):
    id: int
    module_id: int | None  # None: course-level material (syllabus, calendar, assignments)
    filename: str
    size_bytes: int
    scan_status: str
    uploaded_at: datetime
    source_url: str | None = None  # a web page added by its address (V7); it can be fetched again


class MaterialsOut(BaseModel):
    index_version: int  # 0: no index built yet
    rebuild_job_id: int | None = None  # a rebuild waiting or running
    materials: list[MaterialOut]


class UploadOut(BaseModel):
    material: MaterialOut
    job_id: int  # the index rebuild


def _services(request: Request):
    return request.app.state.services


def _out(row: Material, data_root=None) -> MaterialOut:
    return MaterialOut(id=row.id, module_id=row.module_id, filename=row.filename, size_bytes=row.size_bytes,
                       scan_status=row.scan_status, uploaded_at=row.uploaded_at,
                       source_url=_source_url(row, data_root) if data_root is not None else None)


def _source_url(row: Material, data_root) -> str | None:
    """The address of a web page material: a `web-*.md` file whose first line is the source comment with an
    https address. Any other file (a PDF named `web-...`) is not a web page; its bytes are never decoded
    beyond a short prefix."""
    if not (row.filename.startswith("web-") and row.filename.endswith(".md")):
        return None
    try:
        with index_jobs.material_path(data_root, row).open("rb") as f:
            first = f.readline(web_pages.MAX_FIRST_LINE)
    except OSError:
        return None
    return web_pages.source_url(first.decode("utf-8", errors="replace"))


class UrlIn(BaseModel):
    url: str = Field(min_length=8, max_length=2000)
    module_id: int | None = None  # None: course-level material


def _module_of(services, course_id: int, module_id: int | None) -> None:
    if module_id is None:
        return
    with Session(services.engine) as db:
        module = db.get(Module, module_id)
    if module is None or module.course_id != course_id:
        raise ApiError(404, ErrorCode.not_found, "module not found")


async def fetch_as_material(url: str, course_type: str) -> tuple[str, bytes]:
    """The page at `url` as a scanned Markdown material: (file name, bytes); ApiError 422 when refused."""
    try:
        page = await web_pages.fetch_page(url)
    except web_pages.PageRefused as e:
        raise ApiError(422, ErrorCode.invalid, str(e)) from None
    data = web_pages.material_text(page).encode("utf-8")
    try:
        name = await asyncio.to_thread(index_jobs.check_upload, web_pages.material_name(page.url), data,
                                       course_type)
    except index_jobs.MaterialRefused as e:
        raise ApiError(422, ErrorCode.invalid, str(e)) from None
    return name, data


@router.get("/courses/{course_id}/materials", response_model=MaterialsOut, operation_id="materials_list")
def list_materials(access: CourseInstructor, request: Request):
    services = _services(request)
    from app.storage.models import Job

    with Session(services.engine) as db:
        rows = db.exec(select(Material).where(Material.course_id == access.course.id)
                       .order_by(col(Material.module_id), col(Material.filename))).all()
        job = db.exec(select(Job).where(Job.kind == index_jobs.REBUILD, Job.course_id == access.course.id,
                                        col(Job.status).in_(["queued", "running"]))
                     .order_by(col(Job.id).desc())).first()  # the newest: it sees every file
    return MaterialsOut(index_version=index_jobs.index_version(services.engine, access.course.id),
                        rebuild_job_id=job.id if job else None,
                        materials=[_out(r, services.settings.data_path()) for r in rows])


@router.post("/courses/{course_id}/materials", response_model=UploadOut, status_code=201,
             operation_id="materials_upload")
async def upload(access: CourseInstructor, request: Request,
                 file: Annotated[UploadFile, File(description="PDF, PPTX, DOCX, Markdown, text or HTML")],
                 module_id: Annotated[int | None, Form()] = None):
    """Refused (422, nothing stored) when the file type is not allowed, it is too large or unreadable, or
    the privacy scan finds student data (the response names the finding types, never the text)."""
    services = _services(request)
    if module_id is not None:
        with Session(services.engine) as db:
            module = db.get(Module, module_id)
        if module is None or module.course_id != access.course.id:
            raise ApiError(404, ErrorCode.not_found, "module not found")
    data = await file.read(MAX_BYTES + 1)
    try:
        # extraction and the privacy scan take seconds on a large file: off the event loop
        name = await asyncio.to_thread(index_jobs.check_upload, file.filename or "", data,
                                       access.course.course_type)
    except index_jobs.MaterialRefused as e:
        raise ApiError(422, ErrorCode.invalid, str(e)) from None
    try:
        row = index_jobs.store(services.engine, services.settings.data_path(), access.course.id, module_id,
                               name, data)
    except FileExistsError:
        raise ApiError(409, ErrorCode.conflict,
                       "a file with this name exists here; delete it first") from None
    job = index_jobs.request_rebuild(services.engine, access.course.id, access.account_id)
    with Session(services.engine) as db:
        db.add(AuditLog(account_id=access.account_id, action="material.upload",
                        target=f"course:{access.course.id}", details={"material_id": row.id}))
        db.commit()
    return UploadOut(material=_out(row, services.settings.data_path()), job_id=job.id)


@router.post("/courses/{course_id}/materials/url", response_model=UploadOut, status_code=201,
             operation_id="materials_add_url",
             responses={409: {"description": "this page was added here already (fetch it again instead)"},
                        422: {"description": "the address or the page is refused, or the scan found "
                                             "student data"}})
async def add_url(body: UrlIn, access: CourseInstructor, request: Request):
    """V7: a web page as course material. The page is fetched once (https, public addresses only, at most
    2 MB, redirects checked), converted to Markdown with its address, scanned like an upload and indexed."""
    services = _services(request)
    _module_of(services, access.course.id, body.module_id)
    name, data = await fetch_as_material(body.url, access.course.course_type)
    try:
        row = index_jobs.store(services.engine, services.settings.data_path(), access.course.id,
                               body.module_id, name, data)
    except FileExistsError:
        raise ApiError(409, ErrorCode.conflict,
                       "this page is in the material already; fetch it again") from None
    job = index_jobs.request_rebuild(services.engine, access.course.id, access.account_id)
    with Session(services.engine) as db:
        db.add(AuditLog(account_id=access.account_id, action="material.add_url",
                        target=f"course:{access.course.id}", details={"material_id": row.id}))
        db.commit()
    return UploadOut(material=_out(row, services.settings.data_path()), job_id=job.id)


@router.post("/courses/{course_id}/materials/{material_id}/refetch", response_model=UploadOut,
             operation_id="materials_refetch",
             responses={422: {"description": "not a web page, or the page is refused now"}})
async def refetch(material_id: int, access: CourseInstructor, request: Request):
    """V7: fetch a web material again from its address and replace its text (scanned again)."""
    services = _services(request)
    root = services.settings.data_path()
    with Session(services.engine) as db:
        row = db.get(Material, material_id)
        if row is None or row.course_id != access.course.id:
            raise ApiError(404, ErrorCode.not_found, "material not found")
        db.expunge(row)
    url = _source_url(row, root)
    if url is None:
        raise ApiError(422, ErrorCode.invalid, "only a web page added by its address can be fetched again")
    _, data = await fetch_as_material(url, access.course.course_type)
    path = index_jobs.material_path(root, row)
    staging = path.with_name(f".{path.name}.{uuid.uuid4().hex}.new")  # one per request
    with Session(services.engine) as db:
        # the fetch took seconds: it may have been deleted meanwhile. The row lock serializes two refetches of
        # the same material, so the file and its size and hash always come from the same response.
        stored = db.exec(select(Material).where(Material.id == material_id).with_for_update()).first()
        if stored is None:
            raise ApiError(404, ErrorCode.not_found, "material not found")
        try:
            staging.write_bytes(data)
            staging.replace(path)  # atomic: the index never sees half a file
        except OSError:
            staging.unlink(missing_ok=True)
            raise
        stored.size_bytes, stored.sha256 = len(data), hashlib.sha256(data).hexdigest()
        stored.uploaded_at = utcnow()
        db.add(stored)
        db.add(AuditLog(account_id=access.account_id, action="material.refetch",
                        target=f"course:{access.course.id}", details={"material_id": material_id}))
        db.commit()
        db.refresh(stored)
        db.expunge(stored)
    job = index_jobs.request_rebuild(services.engine, access.course.id, access.account_id)
    return UploadOut(material=_out(stored, root), job_id=job.id)


@router.delete("/courses/{course_id}/materials/{material_id}", status_code=204,
               operation_id="materials_delete")
def delete_material(material_id: int, access: CourseInstructor, request: Request):
    """Delete the file and rebuild the index without it (old index versions with its text are removed)."""
    services = _services(request)
    with Session(services.engine) as db:
        # the same row lock as a refetch: the file is removed only after a running refetch replaced it, so a
        # refetch can never write the file of a deleted material back
        row = db.exec(select(Material).where(Material.id == material_id).with_for_update()).first()
        if row is None or row.course_id != access.course.id:
            raise ApiError(404, ErrorCode.not_found, "material not found")
        index_jobs.material_path(services.settings.data_path(), row).unlink(missing_ok=True)
        db.delete(row)
        db.add(AuditLog(account_id=access.account_id, action="material.delete",
                        target=f"course:{access.course.id}", details={"material_id": material_id}))
        db.commit()
    index_jobs.request_rebuild(services.engine, access.course.id, access.account_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
