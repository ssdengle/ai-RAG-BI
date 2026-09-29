from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from apps.api.app.core.auth.service import AuthService
from apps.api.app.core.platform import get_auth_service
from apps.api.app.schemas.auth import LoginRequest, RefreshTokenRequest, TokenResponse


router = APIRouter(prefix="/v1/auth", tags=["authentication"])


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    tokens = await auth_service.login(username=payload.username, password=payload.password)
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
        expires_in=tokens.expires_in,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    payload: RefreshTokenRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    tokens = await auth_service.refresh(refresh_token=payload.refresh_token)
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
        expires_in=tokens.expires_in,
    )
