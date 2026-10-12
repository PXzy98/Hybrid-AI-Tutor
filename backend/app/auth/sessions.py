"""Server-side login sessions. The browser holds a random token; the DB holds only its SHA-256 hash."""
import hashlib
import secrets
from datetime import timedelta

from sqlmodel import Session, delete, select

from app.storage.models import Account, AuthSession, as_utc, utcnow


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(db: Session, account_id: int, ttl_hours: float) -> str:
    token = secrets.token_urlsafe(32)
    db.add(AuthSession(token_hash=token_hash(token), account_id=account_id,
                       expires_at=utcnow() + timedelta(hours=ttl_hours)))
    return token


def resolve(db: Session, token: str | None) -> tuple[Account, AuthSession] | None:
    """The active account behind a token, or None (unknown, expired or deactivated)."""
    if not token:
        return None
    row = db.exec(select(AuthSession).where(AuthSession.token_hash == token_hash(token))).first()
    if row is None:
        return None
    if as_utc(row.expires_at) <= utcnow():
        db.delete(row)
        db.commit()
        return None
    account = db.get(Account, row.account_id)
    if account is None or not account.active:
        return None
    return account, row


def revoke(db: Session, token: str | None) -> None:
    if token:
        db.exec(delete(AuthSession).where(AuthSession.token_hash == token_hash(token)))


def revoke_all(db: Session, account_id: int, keep_hash: str | None = None) -> None:
    stmt = delete(AuthSession).where(AuthSession.account_id == account_id)
    if keep_hash:
        stmt = stmt.where(AuthSession.token_hash != keep_hash)
    db.exec(stmt)


def purge_expired(db: Session) -> None:
    db.exec(delete(AuthSession).where(AuthSession.expires_at <= utcnow()))
