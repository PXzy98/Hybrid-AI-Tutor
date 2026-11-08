"""Task Z8: the worker process takes part in the component loop and reports its health."""
import threading
import time

from sqlmodel import Session, select

from app import worker
from app.storage.models import ProcessStatus


def test_the_worker_heartbeats_and_its_health_check_follows(use_config, tmp_path, monkeypatch):
    monkeypatch.setattr(worker, "HEARTBEAT", tmp_path / "alive")
    use_config({"limits": {"settings": {"poll_seconds": 0.2}}})
    assert worker.check() == 1  # never ran
    stop = threading.Event()
    seen = {}

    def stop_after_first_round():
        for _ in range(1200):  # building the services loads models: allow up to two minutes
            if (tmp_path / "alive").exists():
                break
            time.sleep(0.1)
        from app.core.config import get_settings
        from app.storage.db import make_engine

        engine = make_engine(get_settings().database_url, pooled=False)
        with Session(engine) as db:
            seen["rows"] = [r.process_id for r in db.exec(select(ProcessStatus)).all()]
        engine.dispose()
        stop.set()

    threading.Thread(target=stop_after_first_round).start()
    worker.run(stop)
    assert any(p.startswith("worker-") for p in seen["rows"]), seen  # it was a live process
    assert worker.check(max_age=60) == 0
    assert worker.check(max_age=-1) == 1  # a stale heartbeat fails the check
