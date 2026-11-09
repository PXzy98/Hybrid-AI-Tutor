"""Background jobs (api-v2.md 3.4 `GET /courses/{course_id}/jobs/{job_id}`; task Z12).

A job is a row in `job`. The api enqueues it; the worker (`app.worker`) claims queued jobs one at a time
(`FOR UPDATE SKIP LOCKED`, so several workers never take the same job) and runs the handler registered for
its `kind`. A handler gets the services and the job; it may report progress. An exception marks the job
failed with a short English message (the exception type and its first line, never course or student text
beyond what the handler put in it).

Handlers register with `@handler("<kind>")` in their own module, listed in HANDLER_MODULES.
"""
import asyncio
import inspect
import logging
from collections.abc import Callable
from datetime import timedelta

from sqlalchemy import text
from sqlmodel import Session

from app.storage.models import Job, utcnow

log = logging.getLogger("app.jobs")

HANDLERS: dict[str, Callable] = {}
HANDLER_MODULES = ("app.instructor_ai.eval",)  # imported before a job runs, so their handlers are known
STALE_AFTER = timedelta(hours=6)  # a running job without an end after this is failed (a worker was stopped)


def handler(kind: str):
    def register(fn: Callable) -> Callable:
        HANDLERS[kind] = fn
        return fn

    return register


def enqueue(engine, kind: str, *, course_id: int | None = None, ref_id: int | None = None,
            created_by: int | None = None) -> Job:
    with Session(engine, expire_on_commit=False) as db:
        job = Job(kind=kind, course_id=course_id, ref_id=ref_id, created_by=created_by)
        db.add(job)
        db.commit()
        return job


def get(engine, job_id: int, course_id: int) -> Job | None:
    with Session(engine) as db:
        job = db.get(Job, job_id)
        return job if job is not None and job.course_id == course_id else None


def set_progress(engine, job_id: int, percent: int) -> None:
    with Session(engine) as db:
        job = db.get(Job, job_id)
        if job is not None:
            job.progress = max(0, min(100, int(percent)))
            db.add(job)
            db.commit()


def _claim(engine) -> int | None:
    with Session(engine) as db:
        row = db.exec(text(
            "UPDATE job SET status = 'running', started_at = now() WHERE id = ("
            " SELECT id FROM job WHERE status = 'queued' ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 1)"
            " RETURNING id")).first()
        db.commit()
        return row[0] if row else None


def _finish(engine, job_id: int, error: str | None) -> None:
    with Session(engine) as db:
        job = db.get(Job, job_id)
        job.status, job.error, job.finished_at = ("failed" if error else "done"), error, utcnow()
        if not error:
            job.progress = 100
        db.add(job)
        db.commit()


def _message(e: Exception) -> str:
    first = (str(e).splitlines() or [""])[0]
    return f"{type(e).__name__}: {first}"[:300]


def run_one(services) -> bool:
    """Claim and run one queued job. Returns False when there was none."""
    import importlib

    for name in HANDLER_MODULES:
        importlib.import_module(name)
    job_id = _claim(services.engine)
    if job_id is None:
        return False
    with Session(services.engine, expire_on_commit=False) as db:
        job = db.get(Job, job_id)
    fn = HANDLERS.get(job.kind)
    try:
        if fn is None:
            raise LookupError(f"no handler for job kind {job.kind!r}")
        result = fn(services, job)
        if inspect.isawaitable(result):
            asyncio.run(result)
        _finish(services.engine, job_id, None)
    except Exception as e:  # noqa: BLE001 - a failed job is reported, the worker keeps running
        log.warning("job %s (%s) failed: %s", job_id, job.kind, type(e).__name__)
        _finish(services.engine, job_id, _message(e))
    return True


def run_pending(services, limit: int = 1000) -> int:
    """Run queued jobs until none is left (tests, scripts). Returns how many ran."""
    n = 0
    while n < limit and run_one(services):
        n += 1
    return n


def fail_stale(engine) -> int:
    """Running jobs that never ended (their worker was stopped) become failed. Returns how many."""
    with Session(engine) as db:
        rows = db.exec(text("UPDATE job SET status = 'failed', error = 'interrupted: the worker stopped',"
                            " finished_at = now() WHERE status = 'running' AND started_at < :t RETURNING id")
                       .bindparams(t=utcnow() - STALE_AFTER)).all()
        db.commit()
        return len(rows)
