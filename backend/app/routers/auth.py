from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    create_token,
    decode_token,
    get_current_user_allow_must_change,
    hash_password,
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


@router.post("/login", response_model=AuthTokenPair)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)) -> AuthTokenPair:
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    must_change = user.must_change_credentials
    return AuthTokenPair(
        access_token=create_token(user.username, "access", must_change=must_change),
        refresh_token=create_token(user.username, "refresh", must_change=must_change),
        must_change_credentials=must_change,
    )


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)) -> AccessTokenResponse:
    payload = decode_token(body.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    username = payload.get("sub")
    # Check current must_change state from DB
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return AccessTokenResponse(
        access_token=create_token(username, "access", must_change=user.must_change_credentials)
    )


@router.post("/change-credentials", response_model=AuthTokenPair)
async def change_credentials(
    body: ChangeCredentialsRequest,
    username: str = Depends(get_current_user_allow_must_change),
    db: AsyncSession = Depends(get_db),
) -> AuthTokenPair:
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Check if new username is taken (by another user)
    if body.new_username != username:
        existing = await db.execute(select(User).where(User.username == body.new_username))
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")

    user.username = body.new_username
    user.password_hash = hash_password(body.new_password)
    user.must_change_credentials = False
    await db.commit()

    return AuthTokenPair(
        access_token=create_token(body.new_username, "access", must_change=False),
        refresh_token=create_token(body.new_username, "refresh", must_change=False),
        must_change_credentials=False,
    )
