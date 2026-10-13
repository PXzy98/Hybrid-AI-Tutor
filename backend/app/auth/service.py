"""Accounts: students and instructors (design §7.5)."""
import logging
import re
import uuid
from datetime import timedelta
from typing import Literal

from sqlalchemy import Engine
from sqlmodel import Session, col, select

from app.auth import passwords
from app.auth import sessions as auth_sessions
from app.auth.purge import purge_student
from app.core.config import Settings
from app.storage.models import Account, as_utc, utcnow

log = logging.getLogger("app.auth")

USERNAME_RE = re.compile(r"^[a-z0-9._-]{3,32}$")
Role = Literal["student", "instructor"]


class AccountError(Exception):
    pass


class InvalidUsername(AccountError):
    pass


class UsernameTaken(AccountError):
    pass


class AccountNotFound(AccountError):
    pass


class InvalidCredentials(AccountError):
    pass


class AccountLocked(AccountError):
    pass


class PasswordPolicyError(AccountError):
    pass


def normalize_username(username: str) -> str:
    u = username.strip().lower()
    if not USERNAME_RE.match(u):
        raise InvalidUsername("username: 3-32 characters from a-z 0-9 . _ -")
    return u


class AccountService:
    def __init__(self, engine: Engine, settings: Settings) -> None:
        self.engine = engine
        self.cfg = settings.auth
        self.settings = settings

    def _db(self) -> Session:
        return Session(self.engine, expire_on_commit=False)

    def check_password_policy(self, password: str, username: str) -> None:
        if len(password) < self.cfg.min_password_length:
            n = self.cfg.min_password_length
            raise PasswordPolicyError(f"password must have at least {n} characters")
        if password.strip().lower() == username.lower():
            raise PasswordPolicyError("password must differ from the username")

    # ------------------------------------------------------------------ create
    def _create(self, db: Session, username: str, display_name: str, role: Role, password: str,
                must_change: bool) -> Account:
        username = normalize_username(username)
        if db.exec(select(Account).where(Account.username == username)).first():
            raise UsernameTaken(username)
        account = Account(
            username=username,
            display_name=display_name.strip() or username,
            role=role,
            password_hash=passwords.hash_password(password),
            student_id=str(uuid.uuid4()) if role == "student" else None,
            must_change_password=must_change,
        )
        db.add(account)
        db.commit()
        db.refresh(account)
        return account

    def create_student(self, username: str, display_name: str) -> tuple[Account, str]:
        """New student with a one-time temporary password (returned once, must be changed at first login)."""
        temp = passwords.temporary_password()
        with self._db() as db:
            return self._create(db, username, display_name, "student", temp, must_change=True), temp

    def create_instructor(self, username: str, password: str, must_change: bool = True) -> Account:
        self.check_password_policy(password, username)
        with self._db() as db:
            return self._create(db, username, username, "instructor", password, must_change)

    def bootstrap_instructor(self) -> bool:
        """Create the first instructor from .env if no instructor exists. Returns True if created."""
        with self._db() as db:
            if db.exec(select(Account).where(Account.role == "instructor")).first():
                return False
        s = self.settings
        if not (s.instructor_username and s.instructor_initial_password):
            log.warning("no instructor account: set INSTRUCTOR_USERNAME and INSTRUCTOR_INITIAL_PASSWORD "
                        "in .env or run `python -m app.auth.cli create-instructor <username>`")
            return False
        self.create_instructor(s.instructor_username, s.instructor_initial_password.get_secret_value())
        log.info("created the first instructor account from .env (password change required at first login)")
        return True

    # ------------------------------------------------------------------- login
    def login(self, username: str, password: str) -> tuple[Account, str]:
        """Check credentials and open a session. Returns the account and the cookie token."""
        try:
            username = normalize_username(username)
        except InvalidUsername:
            passwords.burn_time(password)
            raise InvalidCredentials() from None
        with self._db() as db:
            account = db.exec(select(Account).where(Account.username == username)).first()
            if account is None or not account.active:
                passwords.burn_time(password)
                raise InvalidCredentials()
            now = utcnow()
            if account.locked_until and as_utc(account.locked_until) > now:
                raise AccountLocked()
            if not passwords.verify_password(account.password_hash, password):
                account.failed_logins += 1
                if account.failed_logins >= self.cfg.max_failed_logins:
                    account.failed_logins = 0
                    account.locked_until = now + timedelta(minutes=self.cfg.lockout_minutes)
                db.add(account)
                db.commit()
                raise InvalidCredentials()
            if passwords.needs_rehash(account.password_hash):
                account.password_hash = passwords.hash_password(password)
            account.failed_logins = 0
            account.locked_until = None
            account.last_login_at = now
            db.add(account)
            auth_sessions.purge_expired(db)
            token = auth_sessions.create_session(db, account.id, self.cfg.session_ttl_hours)
            db.commit()
            return account, token

    def logout(self, token: str | None) -> None:
        with self._db() as db:
            auth_sessions.revoke(db, token)
            db.commit()

    def resolve(self, token: str | None):
        with self._db() as db:
            return auth_sessions.resolve(db, token)

    # ---------------------------------------------------------------- password
    def change_password(self, account_id: int, current: str, new: str,
                        keep_token_hash: str | None) -> Account:
        """Change one's own password; ends all other sessions of the account."""
        with self._db() as db:
            account = self._get(db, account_id)
            if not passwords.verify_password(account.password_hash, current):
                raise InvalidCredentials()
            if new == current:
                raise PasswordPolicyError("the new password must differ from the current one")
            self.check_password_policy(new, account.username)
            account.password_hash = passwords.hash_password(new)
            account.must_change_password = False
            db.add(account)
            auth_sessions.revoke_all(db, account.id, keep_hash=keep_token_hash)
            db.commit()
            return account

    def set_password(self, account_id: int, new: str, must_change: bool) -> Account:
        """Set a password directly (CLI recovery, tests). Ends all sessions and clears a lockout."""
        with self._db() as db:
            account = self._get(db, account_id)
            self.check_password_policy(new, account.username)
            account.password_hash = passwords.hash_password(new)
            account.must_change_password = must_change
            account.failed_logins, account.locked_until = 0, None
            db.add(account)
            auth_sessions.revoke_all(db, account.id)
            db.commit()
            return account

    # ------------------------------------------------- instructor: student accounts
    def _get(self, db: Session, account_id: int, role: Role | None = None) -> Account:
        account = db.get(Account, account_id)
        if account is None or (role and account.role != role):
            raise AccountNotFound(account_id)
        return account

    def get_by_username(self, username: str) -> Account:
        with self._db() as db:
            account = db.exec(select(Account).where(Account.username == normalize_username(username))).first()
        if account is None:
            raise AccountNotFound(username)
        return account

    def identity_terms(self, student_id: str | None) -> tuple[list[str], list[str]]:
        """(names, usernames) of this student, for the privacy filter: a student who types their own name
        or username gets it redacted even when NER misses it (E4). Read per request, kept in memory only."""
        if not student_id:
            return [], []
        with self._db() as db:
            a = db.exec(select(Account).where(Account.student_id == student_id)).first()
        if a is None:
            return [], []
        names = [a.display_name.strip()] if a.display_name.strip() else []
        names += [w for w in a.display_name.split() if len(w) >= 3]
        return list(dict.fromkeys(names)), [a.username]

    def list_students(self) -> list[Account]:
        with self._db() as db:
            return list(db.exec(select(Account).where(Account.role == "student")
                                .order_by(col(Account.username))).all())

    def reset_student_password(self, account_id: int) -> str:
        temp = passwords.temporary_password()
        with self._db() as db:
            account = self._get(db, account_id, role="student")
            account.password_hash = passwords.hash_password(temp)
            account.must_change_password = True
            account.failed_logins, account.locked_until = 0, None
            db.add(account)
            auth_sessions.revoke_all(db, account.id)
            db.commit()
        return temp

    def update_student(self, account_id: int, display_name: str | None = None,
                       active: bool | None = None) -> Account:
        with self._db() as db:
            account = self._get(db, account_id, role="student")
            if display_name is not None:
                account.display_name = display_name.strip() or account.username
            if active is not None:
                account.active = active
                if not active:
                    auth_sessions.revoke_all(db, account.id)
            db.add(account)
            db.commit()
            return account

    def delete_student(self, account_id: int) -> dict[str, int]:
        """Delete the account, its sessions and all data keyed by its student_id (request_log anonymized)."""
        with self._db() as db:
            account = self._get(db, account_id, role="student")
            auth_sessions.revoke_all(db, account.id)
            counts = purge_student(db, account.student_id)  # includes the account row itself
            db.commit()
        return counts
