"""Courses, members, invitation codes and joining a course (course-structure.md 3.2 and 3.3; task Z9).

Identity data stays in `account` (privacy invariant 6): a membership holds an e-mail only while it is pending
(no account yet) and loses it when the account is linked. A roster CSV keeps only the `email` column (and
reads `display_name`); every other column is ignored and never stored.

The invitation code is stored only as a SHA-256 hash, like a session token: it is shown once, when it is
created, and an instructor who lost it rotates it.
"""
import csv
import hashlib
import io
import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, delete, select

from app.auth.service import AccountService, PasswordPolicyError
from app.catalog import create_course
from app.core.config import AccountLimits
from app.platform.settings import COURSE_TYPES
from app.storage.models import Account, Course, CourseInvite, CourseMember, utcnow

EMAIL_RE = re.compile(r"^[a-z0-9._%+'-]+@[a-z0-9.-]+\.[a-z]{2,}$")
# no look-alike characters (0/o, 1/l/i), so the code can be read out in class or typed from a slide
INVITE_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"
JOIN_REFUSED = "the invitation code is invalid or expired, or this e-mail is not on the course list"
ACCOUNT_EXISTS = "an account with this e-mail exists: log in and enter the code there"


class CourseError(Exception):
    """A request that cannot be done as asked (HTTP 422)."""


class CourseNotFound(CourseError):
    """HTTP 404."""


class CourseConflict(CourseError):
    """HTTP 409: clashes with the current state (a taken course code, the last instructor, ...)."""


class JoinRefused(CourseError):
    """HTTP 400; the message does not say which check failed unless the caller can act on it."""


@dataclass(frozen=True)
class CourseView:
    id: int
    code: str
    title: str
    term_label: str
    course_type: str
    visibility_mode: str
    status: str
    my_role: str | None  # the caller's role in the course; "instructor" for an admin


@dataclass(frozen=True)
class MemberView:
    id: int
    role: str
    status: str
    account_id: int | None
    username: str | None
    display_name: str | None
    email: str | None  # the account's e-mail, or the invited e-mail while pending
    created_at: datetime


@dataclass(frozen=True)
class InviteView:
    expires_at: datetime | None
    uses: int
    max_uses: int | None
    created_at: datetime
    expired: bool


@dataclass
class ImportReport:
    added: list[str] = field(default_factory=list)  # existing accounts, now active members
    pending: list[str] = field(default_factory=list)  # no account yet: activation with the invitation code
    unchanged: list[str] = field(default_factory=list)  # already on the course list
    rejected: list[dict] = field(default_factory=list)  # {"row": n, "email": raw, "reason": ...}


def normalize_email(raw: str, allowed_domains: list[str]) -> str:
    email = (raw or "").strip().lower()
    if not EMAIL_RE.match(email):
        raise CourseError("not a valid e-mail address")
    if email.rsplit("@", 1)[1] not in {d.strip().lower() for d in allowed_domains}:
        raise CourseError("e-mail domain not allowed")
    return email


def invite_hash(code: str) -> str:
    normalized = re.sub(r"[\s-]", "", code or "").lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _course_view(course: Course, my_role: str | None) -> CourseView:
    return CourseView(course.id, course.code, course.title, course.term_label, course.course_type,
                      course.visibility_mode, course.status, my_role)


def _invite_view(invite: CourseInvite) -> InviteView:
    expired = invite.expires_at is not None and invite.expires_at <= utcnow()
    return InviteView(invite.expires_at, invite.uses, invite.max_uses, invite.created_at, expired)


class CourseService:
    def __init__(self, engine, accounts: AccountService, limits: AccountLimits, enabled_course_types) -> None:
        self.engine = engine
        self.accounts = accounts
        self.limits = limits
        self._enabled_course_types = enabled_course_types  # () -> list[str] | None (system settings)

    def _db(self) -> Session:
        return Session(self.engine, expire_on_commit=False)

    @staticmethod
    def _course(db: Session, course_id: int) -> Course:
        course = db.get(Course, course_id)
        if course is None:
            raise CourseNotFound("course not found")
        return course

    # ---------------------------------------------------------------------------------------- courses
    def visible_courses(self, account_id: int) -> list[CourseView]:
        """Admin: every course. Others: courses with an active membership (students: active courses)."""
        with self._db() as db:
            account = db.get(Account, account_id)
            if account is None:
                return []
            if account.role == "admin":
                courses = db.exec(select(Course).order_by(col(Course.code))).all()
                return [_course_view(c, "instructor") for c in courses]
            rows = db.exec(select(Course, CourseMember.role)
                           .join(CourseMember, CourseMember.course_id == Course.id)
                           .where(CourseMember.account_id == account_id, CourseMember.status == "active")
                           .order_by(col(Course.code))).all()
            return [_course_view(c, role) for c, role in rows if c.status == "active" or role == "instructor"]

    def get(self, course_id: int, my_role: str | None = None) -> CourseView:
        with self._db() as db:
            return _course_view(self._course(db, course_id), my_role)

    def create(self, account_id: int, *, code: str, title: str, course_type: str,
               term_label: str = "") -> CourseView:
        """The creator becomes the first instructor member (course-structure.md 3.2)."""
        code, title = code.strip(), title.strip()
        if not code or not title:
            raise CourseError("a course needs a code and a title")
        enabled = self._enabled_course_types() or list(COURSE_TYPES)
        if course_type not in enabled:
            raise CourseError(f"course type {course_type!r} is not enabled on this system")
        with self._db() as db:
            if db.exec(select(Course).where(Course.code == code)).first() is not None:
                raise CourseConflict("a course with this code exists")
            course = create_course(db, code=code, title=title, course_type=course_type,
                                   term_label=term_label.strip())
            db.add(CourseMember(course_id=course.id, account_id=account_id, role="instructor",
                                status="active"))
            try:
                db.commit()
            except IntegrityError:
                raise CourseConflict("a course with this code exists") from None
            return _course_view(course, "instructor")

    def update(self, course_id: int, *, code: str | None = None, title: str | None = None,
               term_label: str | None = None) -> CourseView:
        with self._db() as db:
            course = self._course(db, course_id)
            if code is not None and code.strip() != course.code:
                if not code.strip():
                    raise CourseError("a course needs a code")
                if db.exec(select(Course).where(Course.code == code.strip())).first() is not None:
                    raise CourseConflict("a course with this code exists")
                course.code = code.strip()
            if title is not None:
                if not title.strip():
                    raise CourseError("a course needs a title")
                course.title = title.strip()
            if term_label is not None:
                course.term_label = term_label.strip()
            db.add(course)
            try:
                db.commit()
            except IntegrityError:
                raise CourseConflict("a course with this code exists") from None
            return _course_view(course, "instructor")

    def archive(self, course_id: int) -> CourseView:
        """Hide a course that will not run again; the term must be ended first (no students left, 3.5)."""
        with self._db() as db:
            course = self._course(db, course_id)
            students = db.exec(select(CourseMember.id).where(CourseMember.course_id == course_id,
                                                             CourseMember.role == "student")).first()
            if students is not None:
                raise CourseConflict("end the term first: the course still has students")
            course.status = "archived"
            db.add(course)
            db.exec(delete(CourseInvite).where(CourseInvite.course_id == course_id))
            db.commit()
            return _course_view(course, "instructor")

    # ---------------------------------------------------------------------------------------- members
    def members(self, course_id: int) -> list[MemberView]:
        with self._db() as db:
            self._course(db, course_id)
            rows = db.exec(select(CourseMember, Account).join(Account, isouter=True,
                                                              onclause=CourseMember.account_id == Account.id)
                           .where(CourseMember.course_id == course_id)
                           .order_by(col(CourseMember.role), col(CourseMember.id))).all()
            return [MemberView(m.id, m.role, m.status, m.account_id, a.username if a else None,
                               a.display_name if a else None, a.email if a else m.email, m.created_at)
                    for m, a in rows]

    def import_roster(self, course_id: int, data: bytes) -> ImportReport:
        """CSV with an `email` column and an optional `display_name` column (course-structure.md 3.3).

        Existing student account -> active member; no account -> pending (activation with the code). The
        display name of a pending row is not stored (the student enters it when he activates); other columns
        are ignored."""
        if len(data) > self.limits.max_roster_bytes:
            raise CourseError(f"the file is larger than {self.limits.max_roster_bytes} bytes")
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise CourseError("the file must be UTF-8 text (CSV)") from None
        reader = csv.DictReader(io.StringIO(text))
        columns = {(h or "").strip().lower(): h for h in (reader.fieldnames or [])}
        if "email" not in columns:
            raise CourseError("the CSV needs an `email` column")
        report = ImportReport()
        seen: set[str] = set()
        with self._db() as db:
            course = self._course(db, course_id)
            if course.status != "active":
                raise CourseError("the course is archived")
            for n, row in enumerate(reader, start=2):  # row 1 is the header
                if n - 1 > self.limits.max_roster_rows:
                    raise CourseError(f"the file has more than {self.limits.max_roster_rows} rows")
                raw = (row.get(columns["email"]) or "").strip()
                if not raw and not any((v or "").strip() for v in row.values() if isinstance(v, str)):
                    continue  # blank line
                try:
                    email = normalize_email(raw, self.limits.allowed_email_domains)
                except CourseError as e:
                    report.rejected.append({"row": n, "email": raw, "reason": str(e)})
                    continue
                if email in seen:
                    report.rejected.append({"row": n, "email": raw, "reason": "duplicate in the file"})
                    continue
                seen.add(email)
                self._import_one(db, course_id, email, n, report)
            db.commit()
        return report

    @staticmethod
    def _import_one(db: Session, course_id: int, email: str, n: int, report: ImportReport) -> None:
        account = db.exec(select(Account).where(Account.email == email)).first()
        if account is not None:
            if account.role != "student":
                report.rejected.append({"row": n, "email": email, "reason": "not a student account"})
                return
            member = db.exec(select(CourseMember).where(CourseMember.course_id == course_id,
                                                        CourseMember.account_id == account.id)).first()
            if member is not None:
                report.unchanged.append(email)
                return
            db.add(CourseMember(course_id=course_id, account_id=account.id, role="student", status="active"))
            report.added.append(email)
            return
        pending = db.exec(select(CourseMember).where(CourseMember.course_id == course_id,
                                                     CourseMember.email == email)).first()
        if pending is not None:
            report.unchanged.append(email)
            return
        db.add(CourseMember(course_id=course_id, email=email, role="student", status="pending"))
        report.pending.append(email)

    def add_instructor(self, course_id: int, email: str) -> MemberView:
        """Add an existing instructor (or admin) account as a co-instructor (course-structure.md 3.2)."""
        email = (email or "").strip().lower()
        with self._db() as db:
            self._course(db, course_id)
            account = db.exec(select(Account).where(Account.email == email)).first()
            if account is None or account.role not in ("instructor", "admin") or not account.active:
                raise CourseNotFound("no instructor account with this e-mail; an admin creates it")
            member = db.exec(select(CourseMember).where(CourseMember.course_id == course_id,
                                                        CourseMember.account_id == account.id)).first()
            if member is not None:
                raise CourseConflict("already a member of the course")
            member = CourseMember(course_id=course_id, account_id=account.id, role="instructor",
                                  status="active")
            db.add(member)
            db.commit()
            return MemberView(member.id, member.role, member.status, account.id, account.username,
                              account.display_name, account.email, member.created_at)

    def _member(self, db: Session, course_id: int, member_id: int) -> CourseMember:
        member = db.get(CourseMember, member_id)
        if member is None or member.course_id != course_id:
            raise CourseNotFound("member not found")
        return member

    def remove_member(self, course_id: int, member_id: int) -> None:
        """Remove a membership (the account stays). The last instructor of a course cannot be removed."""
        with self._db() as db:
            member = self._member(db, course_id, member_id)
            if member.role == "instructor":
                others = db.exec(select(CourseMember.id).where(
                    CourseMember.course_id == course_id, CourseMember.role == "instructor",
                    CourseMember.status == "active", CourseMember.id != member_id)).first()
                if others is None:
                    raise CourseConflict("a course keeps at least one instructor")
            db.delete(member)
            db.commit()

    def reset_student_password(self, course_id: int, member_id: int) -> str:
        """A temporary password for a student member (must be changed at the next login)."""
        with self._db() as db:
            member = self._member(db, course_id, member_id)
            account = db.get(Account, member.account_id) if member.account_id else None
            if member.role != "student" or account is None or account.role != "student":
                raise CourseError("only an active student member's password can be reset")
        return self.accounts.reset_student_password(account.id)

    # ------------------------------------------------------------------------------ invitation code
    def invite(self, course_id: int) -> InviteView | None:
        with self._db() as db:
            self._course(db, course_id)
            row = db.exec(select(CourseInvite).where(CourseInvite.course_id == course_id)).first()
            return _invite_view(row) if row else None

    def rotate_invite(self, course_id: int) -> tuple[str, InviteView]:
        """A new code for the course; the old one stops working. Returns the code (shown once) and its
        view."""
        length = self.limits.invite_code_length
        with self._db() as db:
            course = self._course(db, course_id)
            if course.status != "active":
                raise CourseError("the course is archived")
            db.exec(delete(CourseInvite).where(CourseInvite.course_id == course_id))
            code = "".join(secrets.choice(INVITE_ALPHABET) for _ in range(length))
            row = CourseInvite(course_id=course_id, code_hash=invite_hash(code), role="student",
                               expires_at=utcnow() + timedelta(days=self.limits.invite_expiry_days))
            db.add(row)
            db.commit()
            return code, _invite_view(row)

    # ----------------------------------------------------------------------------------------- join
    def _valid_invite(self, db: Session, code: str) -> tuple[CourseInvite, Course]:
        row = db.exec(select(CourseInvite).where(CourseInvite.code_hash == invite_hash(code))).first()
        if row is None or (row.expires_at is not None and row.expires_at <= utcnow()) or \
                (row.max_uses is not None and row.uses >= row.max_uses):
            raise JoinRefused(JOIN_REFUSED)
        course = db.get(Course, row.course_id)
        if course is None or course.status != "active":
            raise JoinRefused(JOIN_REFUSED)
        return row, course

    def join_existing(self, account_id: int, code: str) -> int:
        """A logged-in student enters a course's code: his pending membership (by his account's e-mail)
        becomes active (course-structure.md 3.3 step 6). Returns the course ID. No account is created and
        the password does not change."""
        with self._db() as db:
            invite, course = self._valid_invite(db, code)
            account = db.get(Account, account_id)
            if account is None or account.role != "student":
                raise JoinRefused("only student accounts join a course with a code")
            active = db.exec(select(CourseMember).where(CourseMember.course_id == course.id,
                                                        CourseMember.account_id == account.id)).first()
            if active is not None:
                return course.id  # already a member
            pending = db.exec(select(CourseMember).where(CourseMember.course_id == course.id,
                                                         CourseMember.email == account.email,
                                                         CourseMember.status == "pending")).first()
            if pending is None:
                raise JoinRefused(JOIN_REFUSED)
            pending.account_id, pending.email, pending.status = account.id, None, "active"
            invite.uses += 1
            db.add_all([pending, invite])
            db.commit()
            return course.id

    def join_new(self, code: str, *, email: str, display_name: str, password: str) -> tuple[Account, int]:
        """A new student activates his account (course-structure.md 3.3 step 5): only an e-mail on the course
        list of the code's course can do this. In one transaction the account is created and every pending
        membership with that e-mail, in any course, is linked to it and becomes active."""
        try:
            email = normalize_email(email, self.limits.allowed_email_domains)
        except CourseError:
            raise JoinRefused(JOIN_REFUSED) from None
        with self._db() as db:
            invite, course = self._valid_invite(db, code)
            if db.exec(select(Account).where(Account.email == email)).first() is not None:
                raise JoinRefused(ACCOUNT_EXISTS)
            pending = db.exec(select(CourseMember).where(CourseMember.email == email,
                                                         CourseMember.status == "pending")).all()
            if not any(m.course_id == course.id for m in pending):
                raise JoinRefused(JOIN_REFUSED)
            try:
                account = self.accounts.create_joined_student(db, email, display_name, password)
            except PasswordPolicyError as e:
                raise CourseError(str(e)) from None
            for m in pending:
                m.account_id, m.email, m.status = account.id, None, "active"
                db.add(m)
            invite.uses += 1
            db.add(invite)
            try:
                db.commit()
            except IntegrityError:  # the same e-mail activated at the same moment
                raise JoinRefused(ACCOUNT_EXISTS) from None
            db.refresh(account)
            return account, course.id
