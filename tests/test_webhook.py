import json
import uuid
from decimal import Decimal

import pytest
from httpx import Response
from sqlalchemy import text
from src.enums import Currency, PaymentStatus
from src.models import Payment
from src.repositories import PaymentRepository
from src.schemas import CreatePaymentRequest
from src.services.payment import PaymentService
from src.services.webhook import WebhookClient
from src.settings import settings

WEBHOOK_URL = "https://example.com/webhook"


@pytest.fixture
def payment() -> Payment:
    return Payment(
        id=uuid.uuid4(),
        amount=Decimal("100.50"),
        currency=Currency.RUB,
        description="test",
        idempotency_key="webhook-test",
        webhook_url=WEBHOOK_URL,
        status=PaymentStatus.SUCCEEDED,
    )


@pytest.fixture(autouse=True)
def instant_backoff(monkeypatch):
    monkeypatch.setattr(settings, "webhook_backoff_base_seconds", 0)


async def test_delivers_from_first_attempt(payment, respx_mock):
    route = respx_mock.post(WEBHOOK_URL).mock(return_value=Response(200))

    result = await WebhookClient().deliver(payment)

    assert result.attempts == 1
    assert result.error is None
    assert route.call_count == 1


async def test_retries_until_success(payment, respx_mock):
    route = respx_mock.post(WEBHOOK_URL).mock(
        side_effect=[Response(500), Response(500), Response(200)],
    )

    result = await WebhookClient().deliver(payment)

    assert result.attempts == 3
    assert result.error is None
    assert route.call_count == 3


async def test_records_error_when_all_attempts_fail(payment, respx_mock):
    route = respx_mock.post(WEBHOOK_URL).mock(return_value=Response(500))

    result = await WebhookClient().deliver(payment)

    assert result.attempts == settings.webhook_max_attempts
    assert result.error
    assert route.call_count == settings.webhook_max_attempts


async def test_payload_contains_payment_result(payment, respx_mock):
    route = respx_mock.post(WEBHOOK_URL).mock(return_value=Response(200))

    await WebhookClient().deliver(payment)

    sent = json.loads(route.calls[0].request.content)
    assert sent == {
        "payment_id": str(payment.id),
        "status": "succeeded",
        "amount": "100.50",
        "currency": "RUB",
    }


async def test_successful_delivery_is_saved(session, payment_body):
    created = await PaymentService(session).create_payment(
        CreatePaymentRequest.model_validate(payment_body),
        "key-webhook-ok",
    )

    await PaymentRepository(session).record_webhook_result(created.id, 2, None)
    await session.commit()

    row = (
        await session.execute(
            text(
                "select webhook_attempts, webhook_delivered_at,"
                " webhook_last_error from payments where id = :i",
            ),
            {"i": created.id},
        )
    ).one()

    assert row.webhook_attempts == 2
    assert row.webhook_delivered_at is not None
    assert row.webhook_last_error is None


async def test_failed_delivery_is_saved(session, payment_body):
    created = await PaymentService(session).create_payment(
        CreatePaymentRequest.model_validate(payment_body),
        "key-webhook-fail",
    )

    await PaymentRepository(session).record_webhook_result(
        created.id,
        3,
        "connection refused",
    )
    await session.commit()

    row = (
        await session.execute(
            text(
                "select webhook_attempts, webhook_delivered_at,"
                " webhook_last_error from payments where id = :i",
            ),
            {"i": created.id},
        )
    ).one()

    assert row.webhook_attempts == 3
    assert row.webhook_delivered_at is None
    assert row.webhook_last_error == "connection refused"
