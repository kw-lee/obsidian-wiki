from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    CurrentUser,
    clear_refresh_cookie,
    create_token,
    decode_token,
    get_current_user_context_allow_must_change,
    get_refresh_token_from_request,
    hash_password,
    normalize_git_display_name,
    normalize_git_email,
    set_refresh_cookie,
    validate_password_strength,
    verify_password,
)
from app.db.models import User
from app.db.session import get_db
from app.schemas import AuthTokenPair
from app.services.rate_limit import (
    RateLimitRule,
    build_identifier,
    clear_failures,
    ensure_not_limited,
    record_failure,
)

router = APIRouter()
LOGIN_RATE_LIMIT = RateLimitRule(bucket="auth-login")
REFRESH_RATE_LIMIT = RateLimitRule(bucket="auth-refresh")
CHANGE_CREDENTIALS_RATE_LIMIT = RateLimitRule(bucket="auth-change-credentials")


class LoginRequest(BaseModel):
    username: str
    password: str


class AccessTokenResponse(BaseModel):
    access_token: str
    username: str
    token_type: str = "bearer"
    must_change_credentials: bool = False


class ChangeCredentialsRequest(BaseModel):
    new_username: str
    new_password: str
    git_display_name: str
    git_email: str


@router.post("/login", response_model=AuthTokenPair)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AuthTokenPair:
    identifier = build_identifier(request, body.username)
    await ensure_not_limited(LOGIN_RATE_LIMIT, identifier)
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        await record_failure(LOGIN_RATE_LIMIT, identifier)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    await clear_failures(LOGIN_RATE_LIMIT, identifier)
    must_change = user.must_change_credentials
    refresh_token = create_token(
        user.id,
        "refresh",
        username=user.username,
        must_change=must_change,
    )
    set_refresh_cookie(response, refresh_token)
    return AuthTokenPair(
        access_token=create_token(
            user.id,
            "access",
            username=user.username,
            must_change=must_change,
        ),
        username=user.username,
        must_change_credentials=must_change,
    )


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AccessTokenResponse:
    identifier = build_identifier(request, "refresh")
    await ensure_not_limited(REFRESH_RATE_LIMIT, identifier)
    try:
        payload = decode_token(get_refresh_token_from_request(request))
    except HTTPException:
        await record_failure(REFRESH_RATE_LIMIT, identifier)
        raise
    if payload.get("type") != "refresh":
        await record_failure(REFRESH_RATE_LIMIT, identifier)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        await record_failure(REFRESH_RATE_LIMIT, identifier)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    username_claim = payload.get("username")
    if username_claim is not None:
        try:
            user_id = int(subject)
        except ValueError as exc:
            await record_failure(REFRESH_RATE_LIMIT, identifier)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
            ) from exc
        result = await db.execute(select(User).where(User.id == user_id))
    else:
        result = await db.execute(select(User).where(User.username == subject))
    user = result.scalar_one_or_none()
    if user is None:
        await record_failure(REFRESH_RATE_LIMIT, identifier)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    await clear_failures(REFRESH_RATE_LIMIT, identifier)
    return AccessTokenResponse(
        access_token=create_token(
            user.id,
            "access",
            username=user.username,
            must_change=user.must_change_credentials,
        ),
        username=user.username,
        must_change_credentials=user.must_change_credentials,
    )


@router.post("/change-credentials", response_model=AuthTokenPair)
async def change_credentials(
    body: ChangeCredentialsRequest,
    request: Request,
    response: Response,
    current_user: CurrentUser = Depends(get_current_user_context_allow_must_change),
    db: AsyncSession = Depends(get_db),
) -> AuthTokenPair:
    identifier = build_identifier(request, current_user.id, current_user.username)
    await ensure_not_limited(CHANGE_CREDENTIALS_RATE_LIMIT, identifier)
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
    try:
        validate_password_strength(body.new_password)
    except HTTPException:
        await record_failure(CHANGE_CREDENTIALS_RATE_LIMIT, identifier)
        raise
    if new_username != user.username:
        existing = await db.execute(select(User).where(User.username == new_username))
        if existing.scalar_one_or_none() is not None:
            await record_failure(CHANGE_CREDENTIALS_RATE_LIMIT, identifier)
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
    await clear_failures(CHANGE_CREDENTIALS_RATE_LIMIT, identifier)
    refresh_token = create_token(user.id, "refresh", username=user.username, must_change=False)
    set_refresh_cookie(response, refresh_token)

    return AuthTokenPair(
        access_token=create_token(user.id, "access", username=user.username, must_change=False),
        username=user.username,
        must_change_credentials=False,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> Response:
    clear_refresh_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
