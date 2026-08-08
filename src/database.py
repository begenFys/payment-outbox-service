from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from src.settings import settings

engine = create_async_engine(
    url=settings.postgres_url,
    pool_size=settings.pool_size,
    max_overflow=settings.max_overflow,
    pool_timeout=30,
    pool_recycle=3600,
    pool_pre_ping=True,
)

async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass
