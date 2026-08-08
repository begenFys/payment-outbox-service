import secrets
from collections.abc import AsyncGenerator
from http import HTTPStatus

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import async_session_maker
from src.settings import settings


async def get_session() -> AsyncGenerator[AsyncSession]:
    async with async_session_maker() as session:
        yield session


async def require_api_key(
    api_key: str | None = Security(
        APIKeyHeader(name="X-API-Key", auto_error=False),
    ),
) -> None:
    if not api_key:
        raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED)

    if not secrets.compare_digest(api_key, settings.api_key.get_secret_value()):
        raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED)
