"""Versioned per-course retrieval core; the v4 worker and privacy profile are injected by Z4/Z11.

This is not an API or upload handler. Callers must authorize course/module membership.
Without an explicitly provided document scanner, publishing an index fails closed.
"""
import asyncio
import json
import os
import shutil
import tempfile
import textwrap
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import RLock

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.core.schemas import Chunk
from app.rag.documents import SUFFIXES, DocumentError, extract_text
from app.rag.medical_hybrid import _chunk_section, _segments

MAX_COURSE_CHARS = 2_000_000
MAX_FILES = 500

# Z11 will supply a wrapper around scan_document(text, privacy_profile(course_type)).
# It returns True only when the full extracted document is accepted for indexing.
DocumentScanner = Callable[[str], bool]
IndexVersion = Callable[[int], int]


@dataclass
class _Snapshot:
    version: int
    passages: list[Chunk]
    word: TfidfVectorizer | None = None
    char: TfidfVectorizer | None = None
    word_matrix: object = None
    char_matrix: object = None


class CourseRetriever:
    """Standalone v4 per-course index core behind the Z-owned upload and job interfaces.

    The object never reads accounts, class membership or learner data. The API layer must
    call require_course_role before retrieval; a document scan must precede index publication.
    """

    def __init__(self, data_root: Path, *, scan: DocumentScanner | None = None,
                 index_version: IndexVersion | None = None) -> None:
        self.data_root = Path(data_root)
        self.scan = scan
        self.index_version = index_version
        self._cache: dict[int, _Snapshot] = {}
        self._lock = RLock()

    def _folder(self, course_id: int) -> Path:
        if type(course_id) is not int or course_id <= 0:
            raise ValueError("course_id must be a positive integer")
        return self.data_root / "courses" / str(course_id)

    def _manifest_version(self, course_id: int) -> int:
        path = self._folder(course_id) / "index" / "current.json"
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
            version = obj["index_version"]
            return version if type(version) is int and version > 0 else 0
        except (FileNotFoundError, ValueError, KeyError, TypeError):
            return 0

    def _current_version(self, course_id: int) -> int:
        version = self.index_version(course_id) if self.index_version else self._manifest_version(course_id)
        return version if type(version) is int and version > 0 else 0

    def _materials(self, course_id: int):
        root = self._folder(course_id) / "materials"
        if not root.is_dir() or root.is_symlink():
            return
        count = 0
        for folder in sorted(root.iterdir()):
            if not folder.is_dir() or folder.is_symlink():
                continue
            name = folder.name
            if name == "_course":
                module_id = None
            elif name.isascii() and name.isdecimal() and int(name) > 0:
                module_id = int(name)
            else:
                continue
            for path in sorted(folder.iterdir()):
                if not path.is_file() or path.is_symlink() or path.suffix.lower() not in SUFFIXES:
                    continue
                count += 1
                if count > MAX_FILES:
                    raise DocumentError("A course can index at most 500 documents.")
                yield module_id, path

    def _passages(self, course_id: int) -> list[Chunk]:
        if self.scan is None:
            raise DocumentError("Course material indexing requires the document privacy scanner.")
        passages: list[Chunk] = []
        total = 0
        for module_id, path in self._materials(course_id):
            suffix = path.suffix.lower()
            pdf, pptx = suffix == ".pdf", suffix == ".pptx"
            # PowerPoint support is supplied by S2; do not require it for existing text uploads.
            content = extract_text(path, preserve_slide_numbers=True) if pptx else (
                extract_text(path, preserve_pdf_pages=pdf)
            )
            # Scan before writing *any* extracted text to persistent index storage.
            if self.scan(content) is not True:
                raise DocumentError(f"Privacy scan rejected course material: {path.name}")
            total += len(content.replace("\f", ""))
            if total > MAX_COURSE_CHARS:
                raise DocumentError("The course exceeds the two-million-character text budget.")
            sections = content.split("\f") if pdf or pptx else [content]
            for number, body in enumerate(sections, 1):
                for heading, sentences in _segments(body, course_headings=True):
                    wrapped = [line for sentence in sentences for line in textwrap.wrap(
                        sentence, width=650, break_long_words=True, break_on_hyphens=False,
                    )]
                    for text in _chunk_section(heading, wrapped, min_chars=1):
                        meta = {"course_id": course_id, "module_id": module_id, "origin": "uploaded"}
                        if pdf:
                            meta["page"] = number
                        elif pptx:
                            meta["slide"] = number
                        source_module = str(module_id) if module_id is not None else "_course"
                        passages.append(Chunk(
                            text=text, source=f"course/{course_id}/{source_module}/{path.name}",
                            topic=f"course:{course_id}", score=0, metadata=meta,
                        ))
        return passages

    def rebuild(self, course_id: int) -> int:
        """Index on the worker thread and atomically publish a complete version; return its version.

        Z4 owns the database index_version update and job status. The caller must increment
        the database version only *after* this method returns successfully.
        """
        base = self._folder(course_id) / "index"
        with self._lock:
            passages = self._passages(course_id)  # fails closed before publishing
            if not passages:
                raise DocumentError("No searchable, scan-approved materials were found for this course.")
            version = self._manifest_version(course_id) + 1
            base.mkdir(parents=True, exist_ok=True)
            staging = Path(tempfile.mkdtemp(dir=base, prefix=".build-"))
            try:
                (staging / "passages.json").write_text(
                    json.dumps([p.model_dump() for p in passages], ensure_ascii=False),
                    encoding="utf-8",
                )
                target = base / f"v{version}"
                if target.exists():
                    shutil.rmtree(target)  # an incomplete prior publication, never the active version
                os.replace(staging, target)
                pointer = base / f".current-{version}.json"
                pointer.write_text(json.dumps({"index_version": version}), encoding="utf-8")
                os.replace(pointer, base / "current.json")
            finally:
                if staging.exists():
                    shutil.rmtree(staging)
            self._cache.pop(course_id, None)
            return version

    async def rebuild_in_worker(self, course_id: int) -> int:
        """Allow the Z4 job worker to build without blocking FastAPI's event loop."""
        return await asyncio.to_thread(self.rebuild, course_id)

    def _snapshot(self, course_id: int) -> _Snapshot:
        version = self._current_version(course_id)
        cached = self._cache.get(course_id)
        if cached and cached.version == version:
            return cached
        result = _Snapshot(version=version, passages=[])
        if version:
            path = self._folder(course_id) / "index" / f"v{version}" / "passages.json"
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                result.passages = [Chunk.model_validate(obj) for obj in raw]
                if any(p.metadata.get("course_id") != course_id for p in result.passages):
                    raise ValueError("course ID mismatch")
            except (OSError, ValueError, TypeError):
                result.passages = []  # corrupted/missing versions fail closed
        if result.passages:
            corpus = [p.text for p in result.passages]
            result.word = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
            result.char = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5))
            result.word_matrix = result.word.fit_transform(corpus)
            result.char_matrix = result.char.fit_transform(corpus)
        self._cache[course_id] = result
        return result

    def retrieve(self, course_id: int, module_id: int | None, query: str, k: int) -> list[Chunk]:
        """Retrieve only from this course and, when selected, the active module + course-level files."""
        if k <= 0 or not query.strip():
            return []
        if module_id is not None and (type(module_id) is not int or module_id <= 0):
            return []
        try:
            with self._lock:
                snap = self._snapshot(course_id)
                if not snap.passages or snap.word is None or snap.char is None:
                    return []
                word = cosine_similarity(snap.word.transform([query]), snap.word_matrix).ravel()
                char = cosine_similarity(snap.char.transform([query]), snap.char_matrix).ravel()
                accepted = []
                for i, chunk in enumerate(snap.passages):
                    belongs = module_id is None or chunk.metadata["module_id"] in (None, module_id)
                    if belongs and (word[i] > 0.001 or char[i] >= 0.70):
                        accepted.append((i, 0.75 * word[i] + 0.25 * char[i]))
                ranked = sorted(accepted, key=lambda item: (-item[1], item[0]))[:k]
                return [snap.passages[i].model_copy(update={"score": round(float(score), 6)})
                        for i, score in ranked]
        except (OSError, ValueError, TypeError):
            return []
