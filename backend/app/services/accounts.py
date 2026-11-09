"""
Account rules shared by self-registration and the Admin add-user operation (Sprint 03 handover
DH-01, DH-03, DH-04): one place validates names, email syntax, passwords and roles, so both
paths reject the same input and never leave a partial record behind.
"""
import re

from sqlalchemy.orm import Session

from app.auth import hash_password
from app.models import User, UserRole

SUPPORTED_ROLES = tuple(r.value for r in UserRole)
MIN_PASSWORD = 6
_LOCAL = r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*"
_LABEL = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
EMAIL_RE = re.compile(rf"^{_LOCAL}@{_LABEL}(?:\.{_LABEL})+$")


class AccountError(ValueError):
    """Input that cannot become an account; the message is safe to show the user."""


def normalise_email(value: str) -> str:
    """Trimmed, lower-case address with a local part, one @ and a dotted domain, or AccountError."""
    email = (value or "").strip().lower()
    if not email:
        raise AccountError("Email is required")
    if len(email) > 100 or len(email.split("@")[0]) > 64 or not EMAIL_RE.match(email):
        raise AccountError("Enter a valid email address, such as name@example.com")
    return email


def normalise_username(value: str) -> str:
    username = (value or "").strip()
    if not username:
        raise AccountError("Username is required")
    if len(username) > 50:
        raise AccountError("Username must be 50 characters or fewer")
    return username


def check_password(value: str) -> str:
    if len(value or "") < MIN_PASSWORD:
        raise AccountError(f"Password must be at least {MIN_PASSWORD} characters")
    return value


def check_role(value) -> str:
    if value not in SUPPORTED_ROLES:
        raise AccountError(f"Role must be one of: {', '.join(SUPPORTED_ROLES)}")
    return value


def create_account(db: Session, username: str, email: str, password: str, role: str) -> User:
    """Validate everything first, then insert in one commit; raises AccountError on any problem."""
    username, email = normalise_username(username), normalise_email(email)
    check_password(password)
    check_role(role)
    if db.query(User).filter(User.email == email).first():
        raise AccountError("Email already registered")
    if db.query(User).filter(User.username == username).first():
        raise AccountError("Username already taken")
    user = User(username=username, email=email, hashed_password=hash_password(password), role=role, is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def unsupported_role_users(db: Session) -> list[User]:
    """Accounts stored with a role the application does not support (reported at startup, never rewritten)."""
    return db.query(User).filter(User.role.notin_(SUPPORTED_ROLES)).all()
