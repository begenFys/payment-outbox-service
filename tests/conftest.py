import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from testcontainers.community.postgres import PostgresContainer


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Помечает `integration` тесты, которым нужна база."""
    for item in items:
        if "session" in getattr(item, "fixturenames", ()):
            item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="session")
def postgres():
    with PostgresContainer("postgres:18", driver="asyncpg") as container:
        yield container


@pytest.fixture(scope="session")
def migrated_url(postgres: PostgresContainer) -> str:
    url = postgres.get_connection_url()
    config = Config(
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "alembic.ini"),
    )
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    return url


@pytest.fixture(scope="session")
async def engine(migrated_url: str):
    engine = create_async_engine(migrated_url)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(engine):
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        yield session


@pytest.fixture(autouse=True)
async def clean_tables(request: pytest.FixtureRequest):
    yield
    if "session" not in request.fixturenames:
        return
    engine = request.getfixturevalue("engine")
    async with engine.begin() as conn:
        await conn.execute(
            text("TRUNCATE TABLE payments, outbox_messages;"),
        )
