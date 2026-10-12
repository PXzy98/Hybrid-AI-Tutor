"""All database access of the learner model. Rows are keyed by the pseudonymous student_id."""
from datetime import datetime

from sqlalchemy import Engine, delete
from sqlmodel import Session, col, select

from app.core.schemas import Evidence, KcState, Preferences
from app.storage.models import (
    Consent,
    EvidenceLog,
    LearnerKcState,
    LearnerPreference,
    LearnerTopicLevel,
    as_utc,
    utcnow,
)

# what reset() clears; consent and the account stay (design §7.4)
LEARNING_TABLES = (LearnerKcState, LearnerTopicLevel, LearnerPreference, EvidenceLog)


class LearnerRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def _db(self) -> Session:
        return Session(self.engine, expire_on_commit=False)

    # ------------------------------------------------------------------ KC state
    def states(self, student_id: str, kc_ids: list[str]) -> dict[str, KcState]:
        """Stored states for the given KCs (KCs never observed are simply missing)."""
        with self._db() as db:
            rows = db.exec(select(LearnerKcState).where(LearnerKcState.student_id == student_id,
                                                        col(LearnerKcState.kc_id).in_(kc_ids))).all()
        return {r.kc_id: KcState(kc_id=r.kc_id, p_mastery=r.p_mastery, level=r.level, n_obs=r.n_obs,
                                 last_seen=r.last_seen) for r in rows}

    def save_state(self, student_id: str, state: KcState) -> None:
        with self._db() as db:
            row = db.exec(select(LearnerKcState).where(LearnerKcState.student_id == student_id,
                                                       LearnerKcState.kc_id == state.kc_id)).first()
            row = row or LearnerKcState(student_id=student_id, kc_id=state.kc_id, p_mastery=0, level="basic")
            row.p_mastery, row.level, row.n_obs, row.last_seen = (state.p_mastery, state.level, state.n_obs,
                                                                  state.last_seen)
            db.add(row)
            db.commit()

    # ------------------------------------------------------------------- evidence
    def log_evidence(self, student_id: str, ev: Evidence, weight: float = 1.0) -> datetime:
        row = EvidenceLog(student_id=student_id, kc_id=ev.kc_id, kind=ev.kind, source=ev.source,
                          item_id=ev.item_id, correct=ev.correct, signal=ev.signal,
                          misconception_id=ev.misconception_id, weight=weight)
        with self._db() as db:
            db.add(row)
            db.commit()
        return row.created_at

    def evidence(self, student_id: str, kc_id: str | None = None) -> list[EvidenceLog]:
        """Evidence rows, oldest first."""
        stmt = select(EvidenceLog).where(EvidenceLog.student_id == student_id)
        if kc_id:
            stmt = stmt.where(EvidenceLog.kc_id == kc_id)
        with self._db() as db:
            return list(db.exec(stmt.order_by(col(EvidenceLog.id))).all())

    def answered_items(self, student_id: str) -> dict[str, datetime]:
        """item_id -> when it was last answered (UTC)."""
        out: dict[str, datetime] = {}
        for row in self.evidence(student_id):
            if row.item_id:
                out[row.item_id] = as_utc(row.created_at)
        return out

    # ---------------------------------------------------------------- topic level
    def topic_level(self, student_id: str, topic: str) -> str | None:
        with self._db() as db:
            row = db.exec(select(LearnerTopicLevel).where(LearnerTopicLevel.student_id == student_id,
                                                          LearnerTopicLevel.topic == topic)).first()
        return row.level if row else None

    def save_topic_level(self, student_id: str, topic: str, level: str) -> None:
        with self._db() as db:
            row = db.exec(select(LearnerTopicLevel).where(LearnerTopicLevel.student_id == student_id,
                                                          LearnerTopicLevel.topic == topic)).first()
            row = row or LearnerTopicLevel(student_id=student_id, topic=topic, level=level)
            row.level, row.updated_at = level, utcnow()
            db.add(row)
            db.commit()

    # ---------------------------------------------------------------- preferences
    def preference_row(self, student_id: str) -> LearnerPreference | None:
        with self._db() as db:
            stmt = select(LearnerPreference).where(LearnerPreference.student_id == student_id)
            return db.exec(stmt).first()

    def save_preferences(self, student_id: str, prefs: Preferences, implicit: dict) -> None:
        with self._db() as db:
            row = db.exec(select(LearnerPreference).where(LearnerPreference.student_id == student_id)).first()
            row = row or LearnerPreference(student_id=student_id)
            row.sequencing, row.detail, row.source = prefs.sequencing, prefs.detail, prefs.source
            row.implicit, row.updated_at = dict(implicit), utcnow()
            db.add(row)
            db.commit()

    # -------------------------------------------------------------------- consent
    def consent(self, student_id: str) -> bool | None:
        with self._db() as db:
            row = db.exec(select(Consent).where(Consent.student_id == student_id)).first()
        return row.given if row else None

    def set_consent(self, student_id: str, given: bool) -> None:
        with self._db() as db:
            row = db.exec(select(Consent).where(Consent.student_id == student_id)).first()
            row = row or Consent(student_id=student_id, given=given)
            row.given, row.updated_at = given, utcnow()
            db.add(row)
            db.commit()

    # ---------------------------------------------------------------------- reset
    def reset(self, student_id: str) -> None:
        """Forget the learning profile (state, evidence, preferences); keep consent and the account."""
        with self._db() as db:
            for table in LEARNING_TABLES:
                db.exec(delete(table).where(table.student_id == student_id))
            db.commit()
