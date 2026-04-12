from datetime import UTC, datetime, timedelta

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import settings

security = HTTPBearer()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def create_token(
    subject: str, token_type: str = "access", *, must_change: bool = False
) -> str:
    now = datetime.now(UTC)
    if token_type == "access":
        expire = now + timedelta(minutes=settings.access_token_expire_minutes)
    else:
        expire = now + timedelta(days=settings.refresh_token_expire_days)
    payload: dict = {
        "sub": subject,
        "type": token_type,
        "exp": expire,
        "iat": now,
    }
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
) -> str:
    payload = decode_token(credentials.credentials)
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    username: str | None = payload.get("sub")
    if username is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    # Block users who must change credentials from accessing other APIs
    if payload.get("must_change"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Credential change required",
        )
    return username


async def get_current_user_allow_must_change(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """Like get_current_user but allows must_change tokens (for change-credentials endpoint)."""
    payload = decode_token(credentials.credentials)
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    username: str | None = payload.get("sub")
    if username is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return username
