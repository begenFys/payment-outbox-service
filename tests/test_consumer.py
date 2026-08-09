import asyncio
import uuid
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker
from src.broker import handlers
from src.broker.setup import PAYMENT_DLQ_NAME
from src.enums import Currency, PaymentStatus
from src.models import Payment
from src.schemas import CreatePaymentRequest, PaymentNewMessage
from src.services.payment import PaymentService, process_payment
from src.services.webhook import WebhookResult


class FakeGateway:
    def __init__(self, status: PaymentStatus = PaymentStatus.SUCCEEDED) -> None:
        self.status = status
        self.calls = 0

    async def process(
        self,
        amount: Decimal,
        currency: Currency,
    ) -> PaymentStatus:
        self.calls += 1
        return self.status


class FakeWebhook:
    def __init__(self) -> None:
        self.calls = 0

    async def deliver(self, payment: Payment) -> WebhookResult:
        self.calls += 1
        return WebhookResult(attempts=1, error=None)


@pytest.mark.parametrize(
    ("headers", "expected"),
    [
        pytest.param({}, 0, id="no_header"),
        pytest.param({"x-death": []}, 0, id="empty_header"),
        pytest.param({"x-death": [{"count": 1}]}, 1, id="one_retry"),
        pytest.param({"x-death": [{"count": 3}]}, 3, id="three_retries"),
    ],
)
def test_count_attempts_reads_x_death(headers, expected):
    assert handlers.count_attempts(headers) == expected


async def test_second_processing_does_not_change_status(
    session,
    engine,
    payment_body,
):
    payment = await PaymentService(session).create_payment(
        CreatePaymentRequest.model_validate(payment_body),
        "key-idempotent-consumer",
    )
    maker = async_sessionmaker(engine, expire_on_commit=False)
    gateway = FakeGateway(PaymentStatus.SUCCEEDED)
    webhook = FakeWebhook()

    first = await process_payment(payment.id, gateway, webhook, maker)
    second = await process_payment(payment.id, gateway, webhook, maker)

    assert first is PaymentStatus.SUCCEEDED
    assert second is None
    assert gateway.calls == 1

    status = (
        await session.execute(
            text("select status from payments where id = :i"),
            {"i": payment.id},
        )
    ).scalar()
    assert status == PaymentStatus.SUCCEEDED


async def test_concurrent_processing_saves_single_result(
    session,
    engine,
    payment_body,
):
    payment = await PaymentService(session).create_payment(
        CreatePaymentRequest.model_validate(payment_body),
        "key-concurrent-consumer",
    )
    maker = async_sessionmaker(engine, expire_on_commit=False)
    gateway = FakeGateway(PaymentStatus.SUCCEEDED)
    webhook = FakeWebhook()

    results = await asyncio.gather(
        process_payment(payment.id, gateway, webhook, maker),
        process_payment(payment.id, gateway, webhook, maker),
    )

    assert results.count(None) == 1
    assert results.count(PaymentStatus.SUCCEEDED) == 1

    processed = (
        await session.execute(
            text(
                "select count(*) from payments where processed_at is not null",
            ),
        )
    ).scalar()
    assert processed == 1


async def test_message_goes_to_dlq_after_max_attempts(monkeypatch):
    published: list[dict[str, Any]] = []

    class SpyBroker:
        async def publish(self, body: Any, **kwargs: Any) -> None:
            published.append({"body": body, **kwargs})

    processed: list[uuid.UUID] = []

    async def fake_process(payment_id, gateway, session_maker):
        processed.append(payment_id)

    monkeypatch.setattr(handlers, "RABBIT_BROKER", SpyBroker())
    monkeypatch.setattr(handlers, "process_payment", fake_process)

    await handlers.handle_payment_message(
        PaymentNewMessage(payment_id=uuid.uuid4()),
        {"x-death": [{"count": 3}]},
        b'{"payment_id": "x"}',
    )

    assert len(published) == 1
    assert published[0]["routing_key"] == PAYMENT_DLQ_NAME
    assert not processed
