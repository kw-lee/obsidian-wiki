from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    CurrentUser,
    create_token,
    decode_token,
    get_current_user_context_allow_must_change,
    hash_password,
    normalize_git_display_name,
    normalize_git_email,
    verify_password,
)
from app.db.models import User
from app.db.session import get_db
from app.schemas import AuthTokenPair

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ChangeCredentialsRequest(BaseModel):
    new_username: str
    new_password: str
    git_display_name: str
    git_email: str


@router.post("/login", response_model=AuthTokenPair)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)) -> AuthTokenPair:
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    must_change = user.must_change_credentials
    return AuthTokenPair(
        access_token=create_token(
            user.id, "access", username=user.username, must_change=must_change
        ),
        refresh_token=create_token(
            user.id, "refresh", username=user.username, must_change=must_change
        ),
        must_change_credentials=must_change,
    )


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)) -> AccessTokenResponse:
    payload = decode_token(body.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    username_claim = payload.get("username")
    if username_claim is not None:
        try:
            user_id = int(subject)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
            ) from exc
        result = await db.execute(select(User).where(User.id == user_id))
    else:
        result = await db.execute(select(User).where(User.username == subject))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return AccessTokenResponse(
        access_token=create_token(
            user.id,
            "access",
            username=user.username,
            must_change=user.must_change_credentials,
        )
    )


@router.post("/change-credentials", response_model=AuthTokenPair)
async def change_credentials(
    body: ChangeCredentialsRequest,
    current_user: CurrentUser = Depends(get_current_user_context_allow_must_change),
    db: AsyncSession = Depends(get_db),
) -> AuthTokenPair:
    user = await db.get(User, current_user.id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Check if new username is taken (by another user)
    new_username = body.new_username.strip()
    if not new_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username cannot be empty",
        )
    if len(body.new_password) < 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 4 characters long",
        )
    if new_username != user.username:
        existing = await db.execute(select(User).where(User.username == new_username))
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already taken",
            )

    user.username = new_username
    user.password_hash = hash_password(body.new_password)
    user.git_display_name = normalize_git_display_name(
        body.git_display_name, fallback_username=new_username
    )
    user.git_email = normalize_git_email(body.git_email)
    user.must_change_credentials = False
    await db.commit()

    return AuthTokenPair(
        access_token=create_token(user.id, "access", username=user.username, must_change=False),
        refresh_token=create_token(user.id, "refresh", username=user.username, must_change=False),
        must_change_credentials=False,
    )
