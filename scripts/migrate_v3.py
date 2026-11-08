"""Migrate a v3 installation (SQLite data/app.db) into the v4 PostgreSQL database (task Z4).

course-structure.md section 11:
1. create the course "General Medical Knowledge" (MED 0000, medical_science, visibility mode A) with the five
   v3 topics as modules, in the v3 order;
2. import content/topics/*/ into its KCs, items and misconceptions (codes unchanged; unreviewed rows
   as draft);
3. copy the accounts;
4. copy learner state, evidence, misconceptions, consent and preferences;
5. copy request logs, survey responses and conversation turns;
6. course materials and the index are registered later (they need the privacy scanner of task Z11);
7. the target must be empty: the script refuses to run on a database that already has accounts or courses.

Login sessions are not copied (everyone logs in again). Learner tables get their course_id column with the
course-scoped learner model (S8/S9); until then their rows are copied as they are.

Run from the repository root, with DATABASE_URL / PGPASSWORD of the new database in .env:
    python scripts/migrate_v3.py --source data/app.db
"""
import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import MetaData, create_engine, func, select, text  # noqa: E402
from sqlmodel import Session, SQLModel  # noqa: E402

from app.catalog import DEMO_COURSE, create_course, import_topics  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.learner.content import load_yaml_topics  # noqa: E402
from app.storage.db import init_db, make_engine  # noqa: E402
from app.storage.models import Account, Course  # noqa: E402

# v3 tables copied as they are, parents first; auth_session is left out on purpose
COPIED = ["account", "learner_preference", "consent", "learner_kc_state", "learner_topic_level",
          "evidence_log", "learner_misconception", "request_log", "session_turn", "survey_response",
          "config_history"]


class MigrationError(RuntimeError):
    pass


def _utc(value):
    """v3 SQLite returns naive datetimes; they were written in UTC."""
    return value.replace(tzinfo=UTC) if isinstance(value, datetime) and value.tzinfo is None else value


def migrate(source: Path, target_engine, *, seed_status: str | None = None) -> dict[str, int]:
    if not source.is_file():
        raise MigrationError(f"v3 database not found: {source}")
    init_db(target_engine)
    with Session(target_engine) as db:
        if db.exec(select(func.count()).select_from(Account)).one()[0] or \
                db.exec(select(func.count()).select_from(Course)).one()[0]:  # step 7
            raise MigrationError("the target database is not empty; migrate into a new database")
    src = create_engine(f"sqlite:///{source.as_posix()}")
    old = MetaData()
    old.reflect(src)
    counts: dict[str, int] = {}
    with Session(target_engine) as db:
        course = create_course(db, **DEMO_COURSE)  # steps 1-2
        topics = load_yaml_topics(get_settings().content_dir())
        counts.update(import_topics(db, course.id, topics, seed_status))
        conn = db.connection()
        for name in COPIED:  # steps 3-5
            if name not in old.tables:
                counts[name] = 0
                continue
            target = SQLModel.metadata.tables[name]
            columns = [c for c in old.tables[name].columns.keys() if c in target.c]
            with src.connect() as s:
                result = s.execute(select(old.tables[name]))
                rows = [{c: _utc(r._mapping[c]) for c in columns} for r in result]
            if rows:
                conn.execute(target.insert(), rows)
                if "id" in target.c:  # explicit IDs were copied: continue the sequence after them
                    conn.execute(text(f"SELECT setval(pg_get_serial_sequence('\"{name}\"', 'id'), "
                                      f"(SELECT COALESCE(MAX(id), 1) FROM \"{name}\"))"))
            counts[name] = len(rows)
        db.commit()
    src.dispose()
    return counts


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", type=Path, default=ROOT / "data" / "app.db", help="v3 SQLite database")
    ap.add_argument("--seed-status", choices=["active"], help="import unreviewed items as active (demo only)")
    a = ap.parse_args(argv)
    settings = get_settings()
    password = settings.pgpassword.get_secret_value() if settings.pgpassword else None
    engine = make_engine(settings.database_url, pooled=False, password=password)
    try:
        counts = migrate(a.source, engine, seed_status=a.seed_status)
    except MigrationError as e:
        print(f"Migration stopped: {e}", file=sys.stderr)
        return 1
    finally:
        engine.dispose()
    for name, n in counts.items():
        print(f"{name}: {n}")
    print("Step 6 (materials and index) waits for the privacy scanner (task Z11).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
