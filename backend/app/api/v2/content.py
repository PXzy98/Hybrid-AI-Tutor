"""Course content (api-v2.md 3.4; course-structure.md 5; task Z9): modules, KCs, check items, misconceptions,
and YAML import/export. Materials are S's endpoints.

Students may list the modules (without the instructor's guideline); everything else is for the course's
instructors. Codes are fixed once created (learner data refers to them). New content is `active` unless the
request says `draft`; publishing a draft is `PATCH {"status": "active"}`. KCs are retired, not deleted.
"""
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.catalog import CatalogError
from app.catalog.editor import CatalogEditor, CatalogNotFound
from app.platform.access import CourseAccess, require_course_role

router = APIRouter(tags=["content"])
CourseInstructor = Annotated[CourseAccess, Depends(require_course_role("instructor"))]
CourseMemberAccess = Annotated[CourseAccess, Depends(require_course_role("instructor", "student"))]

Code = Annotated[str, Field(pattern=r"^[A-Za-z0-9._-]{1,64}$")]
Level = Literal["basic", "intermediate", "advanced"]
OptionKey = Literal["A", "B", "C", "D"]
Status = Literal["draft", "active", "retired"]


def _editor(request: Request) -> CatalogEditor:
    return CatalogEditor(request.app.state.services.engine)


# -------------------------------------------------------------------------------------------- modules
class ModuleOut(BaseModel):
    id: int
    code: str
    title: str
    position: int
    guideline: str | None  # instructors only


class ModuleIn(BaseModel):
    code: Code
    title: str = Field(min_length=1, max_length=200)
    guideline: str = Field("", max_length=4000)


class ModulePatch(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    guideline: str | None = Field(None, max_length=4000)


class ReorderIn(BaseModel):
    module_ids: list[int]


def _module_out(m, instructor: bool = True) -> ModuleOut:
    return ModuleOut(id=m.id, code=m.code, title=m.title, position=m.position,
                     guideline=m.guideline if instructor else None)


@router.get("/courses/{course_id}/modules", response_model=list[ModuleOut], operation_id="modules_list")
def list_modules(request: Request, access: CourseMemberAccess):
    return [_module_out(m, access.role == "instructor") for m in _editor(request).modules(access.course.id)]


@router.post("/courses/{course_id}/modules", response_model=ModuleOut, status_code=201,
             operation_id="modules_create")
def create_module(request: Request, body: ModuleIn, access: CourseInstructor):
    return _module_out(_editor(request).create_module(access.course.id, **body.model_dump()))


@router.patch("/courses/{course_id}/modules/{module_id}", response_model=ModuleOut,
              operation_id="modules_update")
def update_module(request: Request, module_id: int, body: ModulePatch, access: CourseInstructor):
    return _module_out(_editor(request).update_module(access.course.id, module_id,
                                                      body.model_dump(exclude_none=True)))


@router.delete("/courses/{course_id}/modules/{module_id}", status_code=204, operation_id="modules_delete",
               responses={409: {"description": "the module still has KCs or materials"}})
def delete_module(request: Request, module_id: int, access: CourseInstructor):
    _editor(request).delete_module(access.course.id, module_id)


@router.post("/courses/{course_id}/modules/reorder", response_model=list[ModuleOut],
             operation_id="modules_reorder")
def reorder_modules(request: Request, body: ReorderIn, access: CourseInstructor):
    return [_module_out(m) for m in _editor(request).reorder_modules(access.course.id, body.module_ids)]


# ------------------------------------------------------------------------------------------------ KCs
class KcOut(BaseModel):
    id: int
    module_id: int | None
    code: str
    name: str
    definition: str
    difficulty: Level
    status: Literal["draft", "active", "retired"]
    prerequisite_ids: list[int]


class KcIn(BaseModel):
    module_id: int
    code: Code
    name: str = Field(min_length=1, max_length=200)
    definition: str = Field("", max_length=4000)
    difficulty: Level
    prerequisite_ids: list[int] = []


class KcPatch(BaseModel):
    module_id: int | None = None
    name: str | None = Field(None, min_length=1, max_length=200)
    definition: str | None = Field(None, max_length=4000)
    difficulty: Level | None = None
    status: Literal["active", "retired"] | None = None
    prerequisite_ids: list[int] | None = None


def _kc_out(row) -> KcOut:
    kc, prereqs = row
    return KcOut(id=kc.id, module_id=kc.module_id, code=kc.code, name=kc.name, definition=kc.definition,
                 difficulty=kc.difficulty, status=kc.status, prerequisite_ids=prereqs)


@router.get("/courses/{course_id}/kcs", response_model=list[KcOut], operation_id="kcs_list")
def list_kcs(request: Request, access: CourseInstructor):
    return [_kc_out(r) for r in _editor(request).kcs(access.course.id)]


@router.get("/courses/{course_id}/kcs/{kc_id}", response_model=KcOut, operation_id="kcs_get")
def get_kc(request: Request, kc_id: int, access: CourseInstructor):
    return _kc_out(_editor(request).kc(access.course.id, kc_id))


@router.post("/courses/{course_id}/kcs", response_model=KcOut, status_code=201, operation_id="kcs_create")
def create_kc(request: Request, body: KcIn, access: CourseInstructor):
    return _kc_out(_editor(request).create_kc(access.course.id, **body.model_dump()))


@router.patch("/courses/{course_id}/kcs/{kc_id}", response_model=KcOut, operation_id="kcs_update")
def update_kc(request: Request, kc_id: int, body: KcPatch, access: CourseInstructor):
    """Change a KC, its prerequisites (the full list), or retire it (`status: retired`)."""
    return _kc_out(_editor(request).update_kc(access.course.id, kc_id, body.model_dump(exclude_none=True)))


# ---------------------------------------------------------------------------------------- check items
class OptionModel(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    misconception: Code | None = None  # the misconception (code) this distractor reveals


class ItemOut(BaseModel):
    id: int
    kc_id: int
    code: str
    level: Level
    stem: str
    options: dict[OptionKey, OptionModel]
    answer: OptionKey
    explanation: str
    status: Status


class ItemIn(BaseModel):
    kc_id: int
    code: Code
    level: Level
    stem: str = Field(min_length=1, max_length=2000)
    options: dict[OptionKey, OptionModel]
    answer: OptionKey
    explanation: str = Field("", max_length=4000)
    status: Literal["draft", "active"] = "active"


class ItemPatch(BaseModel):
    kc_id: int | None = None
    level: Level | None = None
    stem: str | None = Field(None, min_length=1, max_length=2000)
    options: dict[OptionKey, OptionModel] | None = None
    answer: OptionKey | None = None
    explanation: str | None = Field(None, max_length=4000)
    status: Status | None = None


def _item_values(body: BaseModel) -> dict:
    values = body.model_dump(exclude_none=True)
    if "options" in values:  # stored like the YAML seed: {"A": {"text": ..., "misconception": ...}}
        values["options"] = {k: {"text": o["text"], "misconception": o.get("misconception")}
                             for k, o in values["options"].items()}
    return values


def _item_out(i) -> ItemOut:
    return ItemOut(id=i.id, kc_id=i.kc_id, code=i.code, level=i.level, stem=i.stem, options=i.options,
                   answer=i.answer, explanation=i.explanation, status=i.status)


@router.get("/courses/{course_id}/check-items", response_model=list[ItemOut], operation_id="check_items_list")
def list_items(request: Request, access: CourseInstructor, kc_id: int | None = None):
    return [_item_out(i) for i in _editor(request).items(access.course.id, kc_id)]


@router.get("/courses/{course_id}/check-items/{item_id}", response_model=ItemOut,
            operation_id="check_items_get")
def get_item(request: Request, item_id: int, access: CourseInstructor):
    for i in _editor(request).items(access.course.id):
        if i.id == item_id:
            return _item_out(i)
    raise CatalogNotFound("check item not found")


@router.post("/courses/{course_id}/check-items", response_model=ItemOut, status_code=201,
             operation_id="check_items_create")
def create_item(request: Request, body: ItemIn, access: CourseInstructor):
    if body.options.get(body.answer) is None:
        raise CatalogError("the answer must be one of the options")
    return _item_out(_editor(request).create_item(access.course.id, _item_values(body)))


@router.patch("/courses/{course_id}/check-items/{item_id}", response_model=ItemOut,
              operation_id="check_items_update")
def update_item(request: Request, item_id: int, body: ItemPatch, access: CourseInstructor):
    """Edit an item; `status: active` publishes a draft, `retired` takes it out of use."""
    return _item_out(_editor(request).update_item(access.course.id, item_id, _item_values(body)))


# ------------------------------------------------------------------------------------- misconceptions
class MisconceptionOut(BaseModel):
    id: int
    kc_id: int
    code: str
    statement: str
    correction: str
    status: Status


class MisconceptionIn(BaseModel):
    kc_id: int
    code: Code
    statement: str = Field(min_length=1, max_length=2000)
    correction: str = Field(min_length=1, max_length=4000)
    status: Literal["draft", "active"] = "active"


class MisconceptionPatch(BaseModel):
    kc_id: int | None = None
    statement: str | None = Field(None, min_length=1, max_length=2000)
    correction: str | None = Field(None, min_length=1, max_length=4000)
    status: Status | None = None


def _mc_out(m) -> MisconceptionOut:
    return MisconceptionOut(id=m.id, kc_id=m.kc_id, code=m.code, statement=m.statement,
                            correction=m.correction, status=m.status)


@router.get("/courses/{course_id}/misconceptions", response_model=list[MisconceptionOut],
            operation_id="misconceptions_list")
def list_misconceptions(request: Request, access: CourseInstructor):
    return [_mc_out(m) for m in _editor(request).misconceptions(access.course.id)]


@router.get("/courses/{course_id}/misconceptions/{misconception_id}", response_model=MisconceptionOut,
            operation_id="misconceptions_get")
def get_misconception(request: Request, misconception_id: int, access: CourseInstructor):
    for m in _editor(request).misconceptions(access.course.id):
        if m.id == misconception_id:
            return _mc_out(m)
    raise CatalogNotFound("misconception not found")


@router.post("/courses/{course_id}/misconceptions", response_model=MisconceptionOut, status_code=201,
             operation_id="misconceptions_create")
def create_misconception(request: Request, body: MisconceptionIn, access: CourseInstructor):
    return _mc_out(_editor(request).create_misconception(access.course.id, body.model_dump()))


@router.patch("/courses/{course_id}/misconceptions/{misconception_id}", response_model=MisconceptionOut,
              operation_id="misconceptions_update")
def update_misconception(request: Request, misconception_id: int, body: MisconceptionPatch,
                         access: CourseInstructor):
    return _mc_out(_editor(request).update_misconception(access.course.id, misconception_id,
                                                         body.model_dump(exclude_none=True)))


# ---------------------------------------------------------------------------------- YAML import/export
class ImportCountsOut(BaseModel):
    modules: int
    kcs: int
    items: int
    misconceptions: int


@router.post("/courses/{course_id}/content/import", response_model=ImportCountsOut,
             operation_id="content_import",
             responses={409: {"description": "the course already has modules"}})
async def import_content(request: Request, access: CourseInstructor,
                         file: Annotated[UploadFile, File(description="ZIP: <module>/kcs.yaml, items.yaml, "
                                                                      "misconceptions.yaml")]):
    """Content in the YAML seed layout into a course without content (one module per folder)."""
    limit = request.app.state.services.settings.limits.content.max_import_bytes
    data = await file.read(limit + 1)
    counts = _editor(request).import_zip(access.course.id, data, max_bytes=limit)
    return ImportCountsOut(**counts.__dict__)


@router.get("/courses/{course_id}/content/export", operation_id="content_export",
            response_class=Response, responses={200: {"content": {"application/zip": {}}}})
def export_content(request: Request, access: CourseInstructor):
    data = _editor(request).export_zip(access.course.id)
    filename = "".join(c if c.isalnum() else "_" for c in access.course.code) + "-content.zip"
    return Response(data, media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})
