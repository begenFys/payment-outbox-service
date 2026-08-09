import asyncio

from src.broker.setup import RABBIT_BROKER, declare_topology
from src.database import async_session_maker
from src.outbox import publish_pending_messages
from src.settings import settings


async def main() -> None:
    await RABBIT_BROKER.connect()
    await declare_topology(RABBIT_BROKER)
    try:
        while True:
            async with async_session_maker() as session:
                published = await publish_pending_messages(
                    session,
                    RABBIT_BROKER,
                )
            if not published:
                await asyncio.sleep(settings.outbox_poll_interval_seconds)
    finally:
        await RABBIT_BROKER.stop()


if __name__ == "__main__":
    asyncio.run(main())
