"""Course material (api-v2.md 3.4; course-structure.md 7): upload, list, delete. Each upload is scanned
before it is stored (`app.rag.index_jobs`); a change starts an index rebuild job (`GET .../jobs/{id}`)."""
import asyncio
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile, status
from pydantic import BaseModel
from sqlmodel import Session, col, select

from app.admin.materials import MAX_BYTES
from app.api.v2.errors import ApiError, ErrorCode
from app.platform.access import CourseAccess, require_course_role
from app.rag import index_jobs
from app.storage.models import AuditLog, Material, Module

router = APIRouter(tags=["materials"])
CourseInstructor = Annotated[CourseAccess, Depends(require_course_role("instructor"))]


class MaterialOut(BaseModel):
    id: int
    module_id: int | None  # None: course-level material (syllabus, calendar, assignments)
    filename: str
    size_bytes: int
    scan_status: str
    uploaded_at: datetime


class MaterialsOut(BaseModel):
    index_version: int  # 0: no index built yet
    rebuild_job_id: int | None = None  # a rebuild waiting or running
    materials: list[MaterialOut]


class UploadOut(BaseModel):
    material: MaterialOut
    job_id: int  # the index rebuild


def _services(request: Request):
    return request.app.state.services


def _out(row: Material) -> MaterialOut:
    return MaterialOut(id=row.id, module_id=row.module_id, filename=row.filename, size_bytes=row.size_bytes,
                       scan_status=row.scan_status, uploaded_at=row.uploaded_at)


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
                        rebuild_job_id=job.id if job else None, materials=[_out(r) for r in rows])


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
    return UploadOut(material=_out(row), job_id=job.id)


@router.delete("/courses/{course_id}/materials/{material_id}", status_code=204,
               operation_id="materials_delete")
def delete_material(material_id: int, access: CourseInstructor, request: Request):
    """Delete the file and rebuild the index without it (old index versions with its text are removed)."""
    services = _services(request)
    with Session(services.engine) as db:
        row = db.get(Material, material_id)
        if row is None or row.course_id != access.course.id:
            raise ApiError(404, ErrorCode.not_found, "material not found")
        index_jobs.material_path(services.settings.data_path(), row).unlink(missing_ok=True)
        db.delete(row)
        db.add(AuditLog(account_id=access.account_id, action="material.delete",
                        target=f"course:{access.course.id}", details={"material_id": material_id}))
        db.commit()
    index_jobs.request_rebuild(services.engine, access.course.id, access.account_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
