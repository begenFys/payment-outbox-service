from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker
from src.enums import OutboxEventType, OutboxStatus
from src.outbox import publish_pending_messages
from src.repositories import OutboxMessageRepository
from src.schemas import CreatePaymentRequest
from src.services.payment import PaymentService


class FakeBroker:
    def __init__(self, error: Exception | None = None) -> None:
        self.published: list[dict[str, Any]] = []
        self.error = error

    async def publish(self, message: dict[str, Any], **kwargs) -> None:
        if self.error is not None:
            raise self.error
        self.published.append({"message": message, **kwargs})


async def test_payment_not_saved_when_outbox_insert_fails(
    session,
    engine,
    payment_body,
    monkeypatch,
):
    async def boom(*args, **kwargs):
        raise RuntimeError("outbox недоступен")

    monkeypatch.setattr(OutboxMessageRepository, "create", boom)

    with pytest.raises(RuntimeError):
        await PaymentService(session).create_payment(
            CreatePaymentRequest.model_validate(payment_body),
            "key-atomic",
        )

    await session.rollback()

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as another_session:
        payments = (
            await another_session.execute(
                text("select count(*) from payments;"),
            )
        ).scalar()
        messages = (
            await another_session.execute(
                text("select count(*) from outbox_messages;"),
            )
        ).scalar()

    assert payments == 0
    assert messages == 0


async def test_publishers_pending_message_and_marks_it_sent(
    session,
    payment_body,
):
    payment = await PaymentService(session).create_payment(
        CreatePaymentRequest.model_validate(payment_body),
        "key-published",
    )

    broker = FakeBroker()
    published = await publish_pending_messages(session, broker)

    assert published == 1

    row = (
        await session.execute(
            text("select status, sent_at from outbox_messages;"),
        )
    ).one()
    assert row.status == OutboxStatus.SENT
    assert row.sent_at is not None

    assert len(broker.published) == 1
    call = broker.published[0]
    assert call["routing_key"] == OutboxEventType.PAYMENT_NEW
    assert call["message"] == {"payment_id": str(payment.id)}


async def test_failed_publish_keeps_message_pending_and_retries_late(
    session,
    payment_body,
):
    await PaymentService(session).create_payment(
        CreatePaymentRequest.model_validate(payment_body),
        "key-failed",
    )

    failing_broker = FakeBroker(error=RuntimeError("брокер лежит"))
    await publish_pending_messages(session, failing_broker)

    row = (
        await session.execute(
            text(
                "select status, retry_count,last_error,next_retry_at "
                "from outbox_messages;",
            ),
        )
    ).one()
    assert row.status == OutboxStatus.PENDING
    assert row.retry_count == 1
    assert row.last_error
    assert row.next_retry_at > datetime.now(UTC)

    await session.execute(
        text("update outbox_messages set next_retry_at = now()"),
    )
    await session.commit()

    published = await publish_pending_messages(session, FakeBroker())
    assert published == 1

    status = (
        await session.execute(
            text("select status from outbox_messages;"),
        )
    ).scalar()
    assert status == OutboxStatus.SENT


async def test_locked_messages_are_skipped_by_another_relay(
    session,
    engine,
    payment_body,
):
    await PaymentService(session).create_payment(
        CreatePaymentRequest.model_validate(payment_body),
        "key-locked",
    )
    first_batch = await OutboxMessageRepository(session).get_pending_batch(10)
    assert len(first_batch) == 1

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as second_session:
        second_batch = await OutboxMessageRepository(
            second_session,
        ).get_pending_batch(10)
        assert not second_batch

    await session.rollback()
