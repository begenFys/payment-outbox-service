import asyncio

from loguru import logger

from src.broker.setup import RABBIT_BROKER, declare_topology
from src.database import async_session_maker
from src.logger import setup_logging
from src.outbox import publish_pending_messages
from src.settings import settings


async def main() -> None:
    setup_logging()
    await RABBIT_BROKER.connect()
    await declare_topology(RABBIT_BROKER)
    logger.info(
        "Relay запущен, опрос outbox каждые {} с",
        settings.outbox_poll_interval_seconds,
    )
    try:
        while True:
            async with async_session_maker() as session:
                published = await publish_pending_messages(
                    session,
                    RABBIT_BROKER,
                )
            if published:
                logger.info("Опубликовано сообщений: {}", published)
            else:
                await asyncio.sleep(settings.outbox_poll_interval_seconds)
    finally:
        await RABBIT_BROKER.stop()
        logger.info("Relay остановлен")


if __name__ == "__main__":
    asyncio.run(main())
