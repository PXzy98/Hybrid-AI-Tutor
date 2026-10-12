"""Course-material uploads and content review status (design §3, §4).

Uploads are stored in <rag.materials_dir>/<topic>/ under a cleaned file name. Indexing belongs to the RAG
owner: if the configured retriever has an `ingest(topic, path)` method it is called; otherwise the file just
waits there for the RAG pipeline.
"""
import asyncio
import logging
import re
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from app.learner.content import ContentStore

log = logging.getLogger("app.admin")

ALLOWED_SUFFIXES = {".md", ".txt", ".pdf", ".html", ".htm", ".docx"}
MAX_BYTES = 20 * 1024 * 1024
SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


class MaterialError(ValueError):
    pass


class MaterialFile(BaseModel):
    name: str
    size_bytes: int
    uploaded_at: datetime


class UploadResult(BaseModel):
    file: MaterialFile
    ingested: bool  # the retriever has ingest() and it succeeded
    ingest_error: str | None = None


class TopicContentStatus(BaseModel):
    topic: str
    name: str
    kcs: int
    items: int
    items_reviewed: int
    misconceptions: int
    misconceptions_reviewed: int
    materials: list[MaterialFile]


class ContentStatus(BaseModel):
    serve_unreviewed: bool  # development/demo: unreviewed items and corrections are shown to students
    topics: list[TopicContentStatus]


def clean_name(filename: str) -> str:
    name = SAFE_NAME_RE.sub("_", Path(filename.replace("\\", "/")).name).strip("._")
    if not name or Path(name).suffix.lower() not in ALLOWED_SUFFIXES:
        raise MaterialError(f"allowed file types: {', '.join(sorted(ALLOWED_SUFFIXES))}")
    return name


def describe(path: Path) -> MaterialFile:
    st = path.stat()
    return MaterialFile(name=path.name, size_bytes=st.st_size,
                        uploaded_at=datetime.fromtimestamp(st.st_mtime, UTC))


def list_materials(folder: Path) -> list[MaterialFile]:
    if not folder.is_dir():
        return []
    return [describe(p) for p in sorted(folder.iterdir()) if p.is_file()]


async def store_upload(folder: Path, filename: str, data: bytes, retriever, topic: str,
                       replace: bool = False) -> UploadResult:
    name = clean_name(filename)
    if not data:
        raise MaterialError("the file is empty")
    if len(data) > MAX_BYTES:
        raise MaterialError(f"the file is larger than {MAX_BYTES // (1024 * 1024)} MB")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    if path.exists() and not replace:
        raise FileExistsError(name)
    path.write_bytes(data)
    ingest = getattr(retriever, "ingest", None)
    if not callable(ingest):
        return UploadResult(file=describe(path), ingested=False)
    try:
        await asyncio.to_thread(ingest, topic, str(path))
    except Exception as e:  # noqa: BLE001  the file is stored either way; indexing can be retried
        log.warning("retriever ingest failed for topic %s (%s)", topic, type(e).__name__)
        return UploadResult(file=describe(path), ingested=False, ingest_error=type(e).__name__)
    return UploadResult(file=describe(path), ingested=True)


def content_status(content: ContentStore, topics: list[str], materials_dir) -> ContentStatus:
    out = []
    for t in topics:
        tc = content.topic(t)
        if tc is None:
            continue
        out.append(TopicContentStatus(
            topic=t, name=tc.name, kcs=len(tc.kcs), items=len(tc.items),
            items_reviewed=sum(i.reviewed for i in tc.items), misconceptions=len(tc.misconceptions),
            misconceptions_reviewed=sum(m.reviewed for m in tc.misconceptions),
            materials=list_materials(materials_dir(t))))
    return ContentStatus(serve_unreviewed=content.serve_unreviewed, topics=out)
