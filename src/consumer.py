import asyncio

from faststream import FastStream

import src.broker.handlers  # noqa: F401  подписчик регистрируется при импорте
from src.broker.setup import RABBIT_BROKER, declare_topology
from src.logger import setup_logging

app = FastStream(RABBIT_BROKER)


@app.after_startup
async def after_startup() -> None:
    setup_logging()
    await declare_topology(RABBIT_BROKER)


if __name__ == "__main__":
    asyncio.run(app.run())
