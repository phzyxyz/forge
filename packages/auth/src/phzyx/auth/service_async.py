"""AsyncAuthService — thin async facade over AuthService for dual-stack apps."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from phzyx.auth.api_keys import IssuedAPIKey
from phzyx.auth.principal import Principal
from phzyx.auth.service import AuthResult, AuthService
from phzyx.auth.tokens import TokenPair


@dataclass
class AsyncAuthService:
    """Mirrors AuthService methods with await; offloads CPU-bound password work."""

    inner: AuthService

    async def register(self, email: str, password: str, **kwargs: Any) -> Principal:
        return await asyncio.to_thread(self.inner.register, email, password, **kwargs)

    async def login(self, email: str, password: str, **kwargs: Any) -> AuthResult:
        return await asyncio.to_thread(self.inner.login, email, password, **kwargs)

    async def logout(self, session_token: str | None) -> None:
        await asyncio.to_thread(self.inner.logout, session_token)

    async def revoke_all_sessions(self, user_id: str) -> int:
        return await asyncio.to_thread(self.inner.revoke_all_sessions, user_id)

    async def resolve_principal(self, **kwargs: Any) -> Principal | None:
        return await asyncio.to_thread(lambda: self.inner.resolve_principal(**kwargs))

    async def change_password(
        self,
        user_id: str,
        current_password: str,
        new_password: str,
        **kwargs: Any,
    ) -> None:
        await asyncio.to_thread(
            self.inner.change_password,
            user_id,
            current_password,
            new_password,
            **kwargs,
        )

    async def request_password_reset(self, email: str, *, ip: str | None = None) -> str | None:
        return await asyncio.to_thread(self.inner.request_password_reset, email, ip=ip)

    async def reset_password(self, token: str, new_password: str) -> None:
        await asyncio.to_thread(self.inner.reset_password, token, new_password)

    async def request_email_verification(self, user_id: str) -> str:
        return await asyncio.to_thread(self.inner.request_email_verification, user_id)

    async def verify_email(self, token: str) -> None:
        await asyncio.to_thread(self.inner.verify_email, token)

    async def create_api_key(
        self, *, name: str, user_id: str | None, scopes: list[str]
    ) -> IssuedAPIKey:
        return await asyncio.to_thread(
            lambda: self.inner.create_api_key(name=name, user_id=user_id, scopes=scopes)
        )

    async def list_api_keys(self, user_id: str) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self.inner.list_api_keys, user_id)

    async def revoke_api_key(self, key_id: str, *, user_id: str | None = None) -> bool:
        return await asyncio.to_thread(lambda: self.inner.revoke_api_key(key_id, user_id=user_id))

    async def refresh_jwt(self, refresh_token: str) -> TokenPair:
        return await asyncio.to_thread(self.inner.refresh_jwt, refresh_token)
