from typing import Any

from faststream import AckPolicy
from faststream.rabbit.annotations import RabbitMessage
from loguru import logger

from src.broker.setup import (
    BASIS_DIRECT,
    PAYMENT_DLQ_NAME,
    PAYMENT_NEW_QUEUE,
    RABBIT_BROKER,
)
from src.database import async_session_maker
from src.schemas import PaymentNewMessage
from src.services.gateway import PaymentGateway
from src.services.payment import process_payment
from src.settings import settings

GATEWAY = PaymentGateway()


def count_attempts(headers: dict[str, Any]) -> int:
    deaths = headers.get("x-death") or []
    if not deaths:
        return 0
    return int(deaths[0].get("count", 0))


@RABBIT_BROKER.subscriber(
    PAYMENT_NEW_QUEUE,
    exchange=BASIS_DIRECT,
    ack_policy=AckPolicy.REJECT_ON_ERROR,
)
async def handle_payment_new(
    body: PaymentNewMessage,
    message: RabbitMessage,
) -> None:
    attemtps = count_attempts(message.headers)
    if attemtps >= settings.consumer_max_attempts:
        logger.error(
            f"Платёж {body.payment_id} не обработан за {attemtps} попыток, "
            f"отправляю в DLQ",
        )
        await RABBIT_BROKER.publish(
            message.body,
            routing_key=PAYMENT_DLQ_NAME,
            exchange=BASIS_DIRECT,
            persist=True,
            mandatory=True,
        )
        return

    await process_payment(body.payment_id, GATEWAY, async_session_maker)
