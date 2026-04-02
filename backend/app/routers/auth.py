from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.auth import create_token, decode_token, verify_password
from app.config import settings

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest) -> TokenResponse:
    if body.username != settings.admin_username or not verify_password(
        body.password, settings.admin_password_hash
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return TokenResponse(
        access_token=create_token(body.username, "access"),
        refresh_token=create_token(body.username, "refresh"),
    )


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(body: RefreshRequest) -> AccessTokenResponse:
    payload = decode_token(body.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    username = payload.get("sub")
    return AccessTokenResponse(access_token=create_token(username, "access"))
