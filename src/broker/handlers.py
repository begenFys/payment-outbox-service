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
from src.services.webhook import WebhookClient
from src.settings import settings

GATEWAY = PaymentGateway()
WEBHOOK = WebhookClient()


def count_attempts(headers: dict[str, Any]) -> int:
    deaths = headers.get("x-death") or []
    if not deaths:
        return 0
    return int(deaths[0].get("count", 0))


async def handle_payment_message(
    body: PaymentNewMessage,
    headers: dict[str, Any],
    raw_body: bytes,
) -> None:
    attempts = count_attempts(headers)
    if attempts >= settings.consumer_max_attempts:
        logger.error(
            f"Платёж {body.payment_id} не обработан за {attempts} попыток, "
            f"отправляю в DLQ",
        )
        await RABBIT_BROKER.publish(
            raw_body,
            routing_key=PAYMENT_DLQ_NAME,
            exchange=BASIS_DIRECT,
            persist=True,
            mandatory=True,
        )
        return

    await process_payment(
        body.payment_id,
        GATEWAY,
        WEBHOOK,
        async_session_maker,
    )


@RABBIT_BROKER.subscriber(
    PAYMENT_NEW_QUEUE,
    exchange=BASIS_DIRECT,
    ack_policy=AckPolicy.REJECT_ON_ERROR,
)
async def handle_payment_new(
    body: PaymentNewMessage,
    message: RabbitMessage,
) -> None:
    await handle_payment_message(body, message.headers, message.body)
