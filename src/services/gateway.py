import asyncio
import random
from decimal import Decimal

from loguru import logger

from src.enums import PaymentStatus
from src.settings import settings


class PaymentGateway:
    async def process(self, amount: Decimal) -> PaymentStatus:
        delay = random.uniform(
            settings.gateway_min_delay_seconds,
            settings.gateway_max_delay_seconds,
        )
        await asyncio.sleep(delay)

        status = (
            PaymentStatus.SUCCEEDED
            if random.random() < settings.gateway_success_rate
            else PaymentStatus.FAILED
        )
        logger.info(
            f"Шлюз обработал платёж на сумму {amount} "
            f"за {delay:.2f}c, результат {status}",
        )
        return status
