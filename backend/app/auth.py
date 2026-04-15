import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import User
from app.db.session import get_db

security = HTTPBearer()
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+$")


@dataclass(frozen=True)
class CurrentUser:
    id: int
    username: str
    git_display_name: str
    git_email: str


def default_git_display_name(username: str) -> str:
    normalized = username.strip()
    return normalized or "Obsidian Wiki"


def default_git_email(username: str) -> str:
    local = "".join(ch.lower() if ch.isalnum() else "-" for ch in username.strip())
    return f"{local.strip('-') or 'user'}@obsidian-wiki.local"


def normalize_git_display_name(value: str | None, *, fallback_username: str) -> str:
    normalized = (value or "").strip()
    return normalized or default_git_display_name(fallback_username)


def normalize_git_email(value: str | None, *, fallback_username: str | None = None) -> str:
    normalized = (value or "").strip()
    if not normalized:
        if fallback_username is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Git email cannot be empty",
            )
        return default_git_email(fallback_username)
    if not _EMAIL_RE.match(normalized):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Git email address",
        )
    return normalized


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def create_token(
    subject: int | str,
    token_type: str = "access",
    *,
    username: str | None = None,
    must_change: bool = False,
) -> str:
    now = datetime.now(UTC)
    if token_type == "access":
        expire = now + timedelta(minutes=settings.access_token_expire_minutes)
    else:
        expire = now + timedelta(days=settings.refresh_token_expire_days)
    payload: dict = {
        "sub": str(subject),
        "type": token_type,
        "exp": expire,
        "iat": now,
    }
    if username is not None:
        payload["username"] = username
    if must_change:
        payload["must_change"] = True
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from e


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> str:
    user = await get_current_user_context(credentials=credentials, db=db)
    return user.username


async def get_current_user_allow_must_change(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> str:
    """Like get_current_user but allows must_change tokens (for change-credentials endpoint)."""
    user = await get_current_user_context_allow_must_change(credentials=credentials, db=db)
    return user.username


async def get_current_user_context(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    payload = decode_token(credentials.credentials)
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    if payload.get("must_change"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Credential change required",
        )
    return await _load_current_user(payload, db)


async def get_current_user_context_allow_must_change(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    payload = decode_token(credentials.credentials)
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    return await _load_current_user(payload, db)


async def _load_current_user(payload: dict, db: AsyncSession) -> CurrentUser:
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    username_claim = payload.get("username")
    if username_claim is not None:
        try:
            user_id = int(subject)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            ) from exc
        result = await db.execute(select(User).where(User.id == user_id))
    else:
        result = await db.execute(select(User).where(User.username == subject))

    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return CurrentUser(
        id=user.id,
        username=user.username,
        git_display_name=normalize_git_display_name(
            user.git_display_name, fallback_username=user.username
        ),
        git_email=normalize_git_email(user.git_email, fallback_username=user.username),
    )
