"""Background worker process (task Z8; guide 4.2): the same image as the api, started as
`python -m app.worker`.

It builds the same services as the api (database, settings, model gateway) and runs the component loop,
so it takes part in live settings switches (course-structure.md 6.5) and shows up in `process_status`.
It also runs the background jobs (`app.platform.jobs`) in a second thread, one at a time, so a long job (an
instructor AI evaluation) never delays the heartbeat. Running now: the instructor AI evaluation (Z12); index
rebuilds, drafts and the daily usage reset are added as their tasks land.

`python -m app.worker --check` is the container health check: the worker touches a heartbeat file on every
round, and the check fails when it is older than three rounds.
"""
import argparse
import logging
import os
import signal
import sys
import tempfile
import threading
import time
from pathlib import Path

HEARTBEAT = Path(os.environ.get("WORKER_HEARTBEAT_FILE", Path(tempfile.gettempdir()) / "tutor-worker.alive"))

log = logging.getLogger("app.worker")


def run(stop: threading.Event | None = None) -> None:
    from app.core.services import build_services

    stop = stop or threading.Event()
    services = build_services()
    manager = services.component_manager
    manager.process_id = "worker-" + manager.process_id
    poll = services.settings.limits.settings.poll_seconds
    log.info("worker started (%s)", manager.process_id)
    from app.platform import jobs

    if jobs.fail_stale(services.engine):
        log.warning("jobs left running by a stopped worker were marked failed")

    def job_loop() -> None:
        while not stop.is_set():
            try:
                if not jobs.run_one(services):
                    stop.wait(poll)
            except Exception:  # noqa: BLE001 - e.g. the database is briefly unreachable
                log.exception("job round failed")
                stop.wait(poll)

    runner = threading.Thread(target=job_loop, name="jobs", daemon=True)
    runner.start()
    try:
        while not stop.is_set():
            try:
                manager.sync()  # heartbeat + live component switch
                HEARTBEAT.write_text(str(time.time()), encoding="utf-8")
            except Exception:  # noqa: BLE001 - the worker must survive a database hiccup
                log.exception("worker round failed")
            stop.wait(poll)
    finally:
        stop.set()
        runner.join(timeout=30)  # a job in progress finishes its current model call
        manager.stop()
        services.engine.dispose()
        log.info("worker stopped")


def check(max_age: float | None = None) -> int:
    from app.core.config import get_settings

    max_age = max_age or 3 * get_settings().limits.settings.poll_seconds
    try:
        age = time.time() - float(HEARTBEAT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 1
    return 0 if age <= max_age else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="health check: exit 0 if the worker is alive")
    a = ap.parse_args(argv)
    if a.check:
        return check()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    run(stop)
    return 0


if __name__ == "__main__":
    sys.exit(main())
