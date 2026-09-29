from __future__ import annotations

from typing import Optional, Protocol

from apps.api.app.core.auth.identity import AuthMethod, UserIdentity, UserRole


class OAuthProvider(Protocol):
    """Placeholder abstraction for external OAuth/OIDC providers."""

    provider_name: str

    async def get_authorization_url(self, *, redirect_uri: str, state: str) -> str:
        """Return the provider authorization URL."""

    async def exchange_code(self, *, code: str, redirect_uri: str) -> UserIdentity:
        """Exchange an authorization code for a platform identity."""


class PlaceholderOAuthProvider:
    """No-op OAuth provider for Sprint 6 — wire a real provider in production."""

    provider_name = "placeholder"

    async def get_authorization_url(self, *, redirect_uri: str, state: str) -> str:
        return f"https://oauth.placeholder/authorize?redirect_uri={redirect_uri}&state={state}"

    async def exchange_code(self, *, code: str, redirect_uri: str) -> UserIdentity:
        return UserIdentity(
            user_id=f"oauth-{code[:8]}",
            username="oauth-user",
            role=UserRole.VIEWER,
            auth_method=AuthMethod.OAUTH,
        )
