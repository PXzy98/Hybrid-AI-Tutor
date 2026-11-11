"""Task Z4: scripts/migrate_v3.py moves a (fictional) v3 SQLite database into the v4 course."""
import importlib.util
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import MetaData, Table, create_engine
from sqlmodel import Session, SQLModel, select

from app.storage.db import make_engine
from app.storage.models import Account, CheckItem, Course, EvidenceLog, LearnerKcState, RequestLog
from app.storage.testing import temporary_database

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "migrate_v3.py"
V3_TABLES = ["account", "auth_session", "learner_preference", "consent", "learner_kc_state",
             "learner_topic_level", "evidence_log", "learner_misconception", "request_log", "session_turn",
             "survey_response", "config_history"]


def _script():
    spec = importlib.util.spec_from_file_location("migrate_v3", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _v3_database(path: Path) -> Path:
    """A v3-shaped SQLite file with one fictional student, naive UTC timestamps as v3 wrote them."""
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    v3 = MetaData()  # v3 had no course: the learner tables come without course_id
    for name in V3_TABLES:
        table = SQLModel.metadata.tables[name]
        Table(name, v3, *[c._copy() for c in table.columns if c.name != "course_id"])
    v3.create_all(engine)
    when = datetime(2026, 10, 20, 12, 0, 0)  # naive, as SQLite returned it in v3
    with engine.begin() as conn:
        conn.execute(SQLModel.metadata.tables["account"].insert(), [
            {"id": 7, "username": "fictional.student", "display_name": "Fictional Student", "role": "student",
             "password_hash": "x", "student_id": "sid-7", "active": True, "must_change_password": False,
             "failed_logins": 0, "created_at": when},
            {"id": 9, "username": "prof", "display_name": "Prof", "role": "instructor", "password_hash": "x",
             "student_id": None, "active": True, "must_change_password": False, "failed_logins": 0,
             "created_at": when}])
        conn.execute(SQLModel.metadata.tables["auth_session"].insert(),
                     [{"token_hash": "h", "account_id": 7, "created_at": when, "expires_at": when}])
        conn.execute(SQLModel.metadata.tables["learner_kc_state"].insert(),
                     [{"student_id": "sid-7", "kc_id": "HBP.1", "p_mastery": 0.6, "level": "intermediate",
                       "n_obs": 3, "last_seen": when}])
        conn.execute(SQLModel.metadata.tables["evidence_log"].insert(),
                     [{"student_id": "sid-7", "kc_id": "HBP.1", "kind": "strong", "source": "check",
                       "item_id": "HBP.1-q1", "correct": True, "weight": 1.0, "created_at": when}])
        conn.execute(SQLModel.metadata.tables["request_log"].insert(),
                     [{"request_id": "r1", "created_at": when, "session_id": "s1", "student_id": "sid-7",
                       "topic": "asthma", "sanitized_question": "What is asthma?", "timings": {},
                       "checks": [], "warnings": []}])
    engine.dispose()
    return path


def test_v3_data_moves_into_the_demo_course_and_a_second_run_is_refused(tmp_path):
    migrate = _script()
    source = _v3_database(tmp_path / "app.db")
    with temporary_database() as url:
        engine = make_engine(url, pooled=False)
        counts = migrate.migrate(source, engine)
        assert counts["account"] == 2 and counts["learner_kc_state"] == 1 and counts["request_log"] == 1
        assert "auth_session" not in counts  # everyone logs in again
        with Session(engine) as db:
            course = db.exec(select(Course)).one()
            assert (course.code, course.title) == ("MED 0000", "General Medical Knowledge")
            assert {i.status for i in db.exec(select(CheckItem)).all()} == {"draft"}
            assert db.get(Account, 7).student_id == "sid-7"
            assert db.get(Account, 7).email == "fictional.student@demo.invalid"
            assert db.get(Account, 9).role == "admin"  # the v3 instructor (section 11 step 3)
            state = db.exec(select(LearnerKcState)).one()
            assert state.last_seen.tzinfo is not None and state.last_seen.hour == 12  # stored as UTC
            assert db.exec(select(EvidenceLog)).one().item_id == "HBP.1-q1"
            assert state.course_id == course.id == db.exec(select(EvidenceLog)).one().course_id
            assert db.exec(select(RequestLog)).one().sanitized_question == "What is asthma?"
            db.add(Account(username="new.one", display_name="N", role="student", password_hash="x"))
            db.commit()  # the ID sequence continues after the copied IDs
            assert db.exec(select(Account).where(Account.username == "new.one")).one().id == 10
        with pytest.raises(migrate.MigrationError, match="not empty"):
            migrate.migrate(source, engine)
        engine.dispose()


def test_a_missing_source_is_reported(tmp_path):
    migrate = _script()
    with temporary_database() as url:
        engine = make_engine(url, pooled=False)
        with pytest.raises(migrate.MigrationError, match="not found"):
            migrate.migrate(tmp_path / "missing.db", engine)
        engine.dispose()
