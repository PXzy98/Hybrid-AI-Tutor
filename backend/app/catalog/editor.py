"""Editing a course's content (api-v2.md 3.4; course-structure.md 5; task Z9): modules, KCs and their
prerequisites, check items, misconceptions, and YAML import/export.

Instructor content is published when it is saved (decision E): new rows are `active` unless the request says
`draft`. Publishing a draft (for example the unreviewed seed items) is a change of its status to `active`.
KCs are retired, never deleted (D6), and codes never change once created: learner state, evidence and
learner misconceptions refer to KCs, items and misconceptions by code (and v1 to modules by code).

Every change runs the same checks as the YAML seed (`app.learner.content.validate`) on the whole course
before it is committed, so an edit can never leave content that the learner model refuses.

The export is a ZIP of the seed layout, `<module code>/{kcs,items,misconceptions}.yaml`; the import reads the
same layout into a course without content (rows without a `status` are imported `active`).
"""
import io
import zipfile
from dataclasses import dataclass

import yaml
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, delete, func, select

from app.catalog import CatalogError, course_topics, import_topics
from app.learner.content import TopicContent, validate
from app.storage.models import CatalogMisconception, CheckItem, Course, Kc, KcPrerequisite, Material, Module

STATUSES = ("draft", "active", "retired")
_FILES = ("kcs.yaml", "items.yaml", "misconceptions.yaml")


class CatalogNotFound(CatalogError):
    """HTTP 404."""


class CatalogConflict(CatalogError):
    """HTTP 409."""


@dataclass(frozen=True)
class ImportCounts:
    modules: int
    kcs: int
    items: int
    misconceptions: int


def _get(db: Session, model, course_id: int, row_id: int, what: str):
    row = db.get(model, row_id)
    if row is None or row.course_id != course_id:
        raise CatalogNotFound(f"{what} not found")
    return row


def _check(db: Session, course_id: int) -> None:
    """The whole course after the change, with the seed checks; raises CatalogError listing the problems."""
    db.flush()
    try:
        topics = course_topics(db, course_id)
    except ValidationError as e:
        raise CatalogError(f"invalid content: {e.errors()[0].get('msg', 'invalid value')}") from None
    problems = validate(topics)
    if problems:
        raise CatalogError("invalid content:\n" + "\n".join(problems))


def _bump(db: Session, course_id: int) -> None:
    """A new content version: running processes reload the course content (app.platform.components)."""
    db.exec(text("UPDATE course SET content_version = content_version + 1 WHERE id = :c")
            .bindparams(c=course_id))


def _commit_checked(db: Session, course_id: int) -> None:
    try:
        _check(db, course_id)  # its flush raises IntegrityError for a duplicate code
        _bump(db, course_id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise CatalogConflict("the code is already used in this course") from None


def _tags_known(db: Session, course_id: int, options: dict) -> None:
    """Misconception tags on options must name a misconception of the course (the loader would drop others
    silently, so check them here)."""
    codes = {o.get("misconception") for o in options.values() if o.get("misconception")}
    if not codes:
        return
    known = set(db.exec(select(CatalogMisconception.code).where(CatalogMisconception.course_id == course_id,
                                                                col(CatalogMisconception.code).in_(codes))))
    unknown = sorted(codes - known)
    if unknown:
        raise CatalogError(f"unknown misconception tag(s): {', '.join(unknown)}")


class CatalogEditor:
    def __init__(self, engine, on_change=None) -> None:
        self.engine = engine
        self._on_change = on_change  # called after every committed change (reload the content at once)

    def _changed(self) -> None:
        if self._on_change is not None:
            self._on_change()

    def _commit(self, db: Session, course_id: int) -> None:
        _commit_checked(db, course_id)
        self._changed()

    def _db(self) -> Session:
        return Session(self.engine, expire_on_commit=False)

    # ---------------------------------------------------------------------------------------- modules
    def modules(self, course_id: int) -> list[Module]:
        with self._db() as db:
            return list(db.exec(select(Module).where(Module.course_id == course_id)
                                .order_by(Module.position, Module.id)).all())

    def create_module(self, course_id: int, *, code: str, title: str, guideline: str = "") -> Module:
        with self._db() as db:
            last = db.exec(select(func.max(Module.position)).where(Module.course_id == course_id)).one()
            module = Module(course_id=course_id, code=code.strip(), title=title.strip(), guideline=guideline,
                            position=(last + 1) if last is not None else 0)
            db.add(module)
            self._commit(db, course_id)
            return module

    def update_module(self, course_id: int, module_id: int, changes: dict) -> Module:
        with self._db() as db:
            module = _get(db, Module, course_id, module_id, "module")
            for name in ("title", "guideline"):
                if name in changes:
                    setattr(module, name, changes[name].strip() if name == "title" else changes[name])
            db.add(module)
            self._commit(db, course_id)
            return module

    def delete_module(self, course_id: int, module_id: int) -> None:
        """Only an empty module (no KCs, retired ones included, and no materials) can be deleted."""
        with self._db() as db:
            module = _get(db, Module, course_id, module_id, "module")
            if db.exec(select(Kc.id).where(Kc.module_id == module_id)).first() is not None:
                raise CatalogConflict("the module has KCs; move or retire them instead")
            if db.exec(select(Material.id).where(Material.module_id == module_id)).first() is not None:
                raise CatalogConflict("the module has materials; delete them first")
            db.delete(module)
            _bump(db, course_id)
            db.commit()
        self._changed()

    def reorder_modules(self, course_id: int, module_ids: list[int]) -> list[Module]:
        with self._db() as db:
            modules = {m.id: m for m in db.exec(select(Module).where(Module.course_id == course_id)).all()}
            if sorted(module_ids) != sorted(modules):
                raise CatalogError("give every module of the course exactly once")
            for position, module_id in enumerate(module_ids):
                modules[module_id].position = position
                db.add(modules[module_id])
            _bump(db, course_id)
            db.commit()
        self._changed()
        return self.modules(course_id)

    # -------------------------------------------------------------------------------------------- KCs
    def kcs(self, course_id: int) -> list[tuple[Kc, list[int]]]:
        """KCs with the IDs of their prerequisites."""
        with self._db() as db:
            kcs = db.exec(select(Kc).where(Kc.course_id == course_id).order_by(Kc.id)).all()
            ids = [k.id for k in kcs]
            edges = db.exec(select(KcPrerequisite).where(col(KcPrerequisite.kc_id).in_(ids))).all()
        prereqs: dict[int, list[int]] = {}
        for e in edges:
            prereqs.setdefault(e.kc_id, []).append(e.prerequisite_id)
        return [(k, sorted(prereqs.get(k.id, []))) for k in kcs]

    def kc(self, course_id: int, kc_id: int) -> tuple[Kc, list[int]]:
        for row in self.kcs(course_id):
            if row[0].id == kc_id:
                return row
        raise CatalogNotFound("KC not found")

    def _set_prerequisites(self, db: Session, course_id: int, kc: Kc, prerequisite_ids: list[int]) -> None:
        for p in prerequisite_ids:
            if p == kc.id:
                raise CatalogError("a KC cannot be its own prerequisite")
            _get(db, Kc, course_id, p, "prerequisite KC")
        db.exec(delete(KcPrerequisite).where(KcPrerequisite.kc_id == kc.id))
        for p in sorted(set(prerequisite_ids)):
            db.add(KcPrerequisite(kc_id=kc.id, prerequisite_id=p))

    def create_kc(self, course_id: int, *, module_id: int, code: str, name: str, difficulty: str,
                  definition: str = "", prerequisite_ids: list[int] = ()) -> tuple[Kc, list[int]]:
        with self._db() as db:
            _get(db, Module, course_id, module_id, "module")
            kc = Kc(course_id=course_id, module_id=module_id, code=code.strip(), name=name.strip(),
                    definition=definition, difficulty=difficulty, status="active")
            db.add(kc)
            try:
                db.flush()
            except IntegrityError:
                raise CatalogConflict("the code is already used in this course") from None
            self._set_prerequisites(db, course_id, kc, list(prerequisite_ids))
            self._commit(db, course_id)
            kc_id = kc.id
        return self.kc(course_id, kc_id)

    def update_kc(self, course_id: int, kc_id: int, changes: dict) -> tuple[Kc, list[int]]:
        with self._db() as db:
            kc = _get(db, Kc, course_id, kc_id, "KC")
            if "module_id" in changes:
                _get(db, Module, course_id, changes["module_id"], "module")
                kc.module_id = changes["module_id"]
            for name in ("name", "definition", "difficulty", "status"):
                if name in changes:
                    setattr(kc, name, changes[name].strip() if name == "name" else changes[name])
            db.add(kc)
            if "prerequisite_ids" in changes:
                self._set_prerequisites(db, course_id, kc, changes["prerequisite_ids"])
            self._commit(db, course_id)
        return self.kc(course_id, kc_id)

    # ----------------------------------------------------------------------------------- check items
    def items(self, course_id: int, kc_id: int | None = None) -> list[CheckItem]:
        with self._db() as db:
            q = select(CheckItem).where(CheckItem.course_id == course_id)
            if kc_id is not None:
                q = q.where(CheckItem.kc_id == kc_id)
            return list(db.exec(q.order_by(CheckItem.id)).all())

    def create_item(self, course_id: int, values: dict) -> CheckItem:
        with self._db() as db:
            _get(db, Kc, course_id, values["kc_id"], "KC")
            _tags_known(db, course_id, values["options"])
            item = CheckItem(course_id=course_id, **{**values, "code": values["code"].strip()})
            db.add(item)
            self._commit(db, course_id)
            return item

    def update_item(self, course_id: int, item_id: int, changes: dict) -> CheckItem:
        with self._db() as db:
            item = _get(db, CheckItem, course_id, item_id, "check item")
            if "kc_id" in changes:
                _get(db, Kc, course_id, changes["kc_id"], "KC")
            if "options" in changes:
                _tags_known(db, course_id, changes["options"])
            for name, value in changes.items():
                if name != "code":
                    setattr(item, name, value)
            db.add(item)
            self._commit(db, course_id)
            return item

    # -------------------------------------------------------------------------------- misconceptions
    def misconceptions(self, course_id: int) -> list[CatalogMisconception]:
        with self._db() as db:
            return list(db.exec(select(CatalogMisconception)
                                .where(CatalogMisconception.course_id == course_id)
                                .order_by(CatalogMisconception.id)).all())

    def create_misconception(self, course_id: int, values: dict) -> CatalogMisconception:
        with self._db() as db:
            _get(db, Kc, course_id, values["kc_id"], "KC")
            row = CatalogMisconception(course_id=course_id, **{**values, "code": values["code"].strip()})
            db.add(row)
            self._commit(db, course_id)
            return row

    def update_misconception(self, course_id: int, misconception_id: int,
                             changes: dict) -> CatalogMisconception:
        with self._db() as db:
            row = _get(db, CatalogMisconception, course_id, misconception_id, "misconception")
            if "kc_id" in changes:
                _get(db, Kc, course_id, changes["kc_id"], "KC")
            for name, value in changes.items():
                if name != "code":
                    setattr(row, name, value)
            db.add(row)
            self._commit(db, course_id)
            return row

    # ----------------------------------------------------------------------------- YAML import/export
    def export_zip(self, course_id: int) -> bytes:
        """Every module with its KCs (retired ones too, with their status), items and misconceptions."""
        with self._db() as db:
            course = db.get(Course, course_id)
            if course is None:
                raise CatalogNotFound("course not found")
            modules = db.exec(select(Module).where(Module.course_id == course_id)
                              .order_by(Module.position, Module.id)).all()
            kcs = db.exec(select(Kc).where(Kc.course_id == course_id).order_by(Kc.id)).all()
            codes = {k.id: k.code for k in kcs}
            edges = db.exec(select(KcPrerequisite).where(col(KcPrerequisite.kc_id).in_(list(codes)))).all()
            items = db.exec(select(CheckItem).where(CheckItem.course_id == course_id)
                            .order_by(CheckItem.id)).all()
            mcs = db.exec(select(CatalogMisconception).where(CatalogMisconception.course_id == course_id)
                          .order_by(CatalogMisconception.id)).all()
        prereqs: dict[int, list[str]] = {}
        for e in edges:
            prereqs.setdefault(e.kc_id, []).append(codes[e.prerequisite_id])
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for m in modules:
                own = [k for k in kcs if k.module_id == m.id]
                ids = {k.id for k in own}
                kc_doc = {"topic": m.code, "name": m.title, "guideline": m.guideline, "position": m.position,
                          "kcs": [{"id": k.code, "name": k.name, "definition": k.definition,
                                   "difficulty": k.difficulty, "prerequisites": sorted(prereqs.get(k.id, [])),
                                   **({"status": k.status} if k.status != "active" else {})} for k in own]}
                item_doc = [{"id": i.code, "kc": codes[i.kc_id], "level": i.level, "stem": i.stem,
                             "options": i.options, "answer": i.answer, "explanation": i.explanation,
                             "status": i.status} for i in items if i.kc_id in ids]
                mc_doc = [{"id": c.code, "kc": codes[c.kc_id], "statement": c.statement,
                           "correction": c.correction, "status": c.status} for c in mcs if c.kc_id in ids]
                for name, doc in zip(_FILES, (kc_doc, item_doc, mc_doc), strict=True):
                    zf.writestr(f"{m.code}/{name}", yaml.safe_dump(doc, allow_unicode=True, sort_keys=False))
        return buffer.getvalue()

    def import_zip(self, course_id: int, data: bytes, *, max_bytes: int) -> ImportCounts:
        """The seed layout into a course without content; one module per folder, ordered by the exported
        `position` (folder name otherwise). A module without KCs (exported before its first KC) is kept."""
        folders = _read_zip(data, max_bytes)
        topics: list[TopicContent] = []
        retired: set[str] = set()
        docs = {}
        for name, files in folders.items():
            kc_doc = files.get("kcs.yaml") or {}
            if not isinstance(kc_doc, dict):
                raise CatalogError(f"{name}/kcs.yaml must be a mapping")
            docs[name] = kc_doc

        def order(name: str):
            position = docs[name].get("position")
            return (position if isinstance(position, int) else 1_000_000, name)

        for name in sorted(folders, key=order):
            files, kc_doc = folders[name], docs[name]
            kcs = []
            for k in kc_doc.get("kcs") or []:
                k = dict(k)
                if k.pop("status", "active") == "retired":
                    retired.add(str(k.get("id")))
                kcs.append(k)
            try:
                topics.append(TopicContent(
                    topic=kc_doc.get("topic", name), name=kc_doc.get("name", name),
                    guideline=kc_doc.get("guideline", ""), kcs=kcs,
                    items=[_with_status(r) for r in files.get("items.yaml") or []],
                    misconceptions=[_with_status(r) for r in files.get("misconceptions.yaml") or []]))
            except (ValidationError, TypeError) as e:
                raise CatalogError(f"{name}: invalid format\n{e}") from None
        if not topics:
            raise CatalogError("the ZIP has no module folder with a kcs.yaml")
        filled = [tp for tp in topics if tp.kcs]
        if len({tp.topic for tp in topics}) != len(topics):
            raise CatalogError("two folders use the same module code")
        with self._db() as db:
            if db.exec(select(Module.id).where(Module.course_id == course_id)).first() is not None:
                raise CatalogConflict("the course already has modules; import into a course without content")
            empty = {"modules": 0, "kcs": 0, "items": 0, "misconceptions": 0}
            counts = import_topics(db, course_id, filled) if filled else empty
            for tp in topics:
                if not tp.kcs:
                    db.add(Module(course_id=course_id, code=tp.topic, title=tp.name, guideline=tp.guideline))
                    counts["modules"] += 1
            db.flush()
            modules = {m.code: m for m in db.exec(select(Module).where(Module.course_id == course_id)).all()}
            for position, tp in enumerate(topics):  # the file's order, empty modules included
                modules[tp.topic].position = position
                db.add(modules[tp.topic])
            for kc in db.exec(select(Kc).where(Kc.course_id == course_id, col(Kc.code).in_(retired))).all():
                kc.status = "retired"
                db.add(kc)
            try:
                _commit_checked(db, course_id)
            except CatalogConflict:
                raise CatalogConflict("a code is used twice in the file") from None
        self._changed()
        return ImportCounts(**counts)


def _with_status(row) -> dict:
    """An instructor's file is his reviewed content: rows without a status are active (decision E)."""
    if not isinstance(row, dict):
        raise CatalogError("items and misconceptions are lists of mappings")
    row = dict(row)
    row.pop("reviewed_by", None)  # v3 seed field
    row["status"] = row.get("status") or "active"
    if row["status"] not in STATUSES:
        raise CatalogError(f"unknown status {row['status']!r}")
    return row


def _read_zip(data: bytes, max_bytes: int) -> dict[str, dict]:
    """{folder: {file name: parsed YAML}} from the upload, read in memory (nothing is extracted to disk).
    Only `<folder>/<kcs|items|misconceptions>.yaml` entries are read; anything else is ignored."""
    if len(data) > max_bytes:
        raise CatalogError(f"the file is larger than {max_bytes} bytes")
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise CatalogError("not a ZIP file") from None
    folders: dict[str, dict] = {}
    total = 0
    with zf:
        for info in zf.infolist():
            parts = info.filename.replace("\\", "/").strip("/").split("/")
            if info.is_dir() or len(parts) < 2 or parts[-1] not in _FILES or ".." in parts:
                continue
            with zf.open(info) as f:
                raw = f.read(max_bytes + 1)  # never trust the sizes in the ZIP header
            total += len(raw)
            if len(raw) > max_bytes or total > max_bytes * 10:
                raise CatalogError("the unpacked files are too large")
            try:
                doc = yaml.safe_load(raw.decode("utf-8"))
            except (UnicodeDecodeError, yaml.YAMLError) as e:
                raise CatalogError(f"{info.filename}: not valid UTF-8 YAML ({type(e).__name__})") from None
            folders.setdefault(parts[-2], {})[parts[-1]] = doc
    return folders
