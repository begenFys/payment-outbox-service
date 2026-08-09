import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.enums import Currency, OutboxEventType, OutboxStatus, PaymentStatus
from src.models import OutboxMessage, Payment
from src.settings import settings


class PaymentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        *,
        amount: Decimal,
        currency: Currency,
        description: str,
        idempotency_key: str,
        webhook_url: str,
        extra_data: dict[str, Any] | None = None,
    ) -> Payment:
        payment = Payment(
            amount=amount,
            currency=currency,
            description=description,
            idempotency_key=idempotency_key,
            webhook_url=webhook_url,
            extra_data=extra_data,
        )
        self.session.add(payment)
        await self.session.flush()
        return payment

    async def get_by_id(self, payment_id: uuid.UUID) -> Payment | None:
        return await self.session.get(Payment, payment_id)

    async def get_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> Payment | None:
        stmt = select(Payment).where(Payment.idempotency_key == idempotency_key)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_processed(
        self,
        payment_id: uuid.UUID,
        status: PaymentStatus,
    ) -> uuid.UUID | None:
        stmt = (
            update(Payment)
            .where(
                Payment.id == payment_id,
                Payment.status == PaymentStatus.PENDING,
            )
            .values(status=status, processed_at=func.now())
            .returning(Payment.id)
            .execution_options(synchronize_session=False)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


MAX_BACKOFF_SECONDS = 10 * 60


class OutboxMessageRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        *,
        event_type: OutboxEventType,
        payload: dict[str, Any],
    ) -> OutboxMessage:
        outbox_message = OutboxMessage(
            event_type=event_type,
            payload=payload,
        )
        self.session.add(outbox_message)
        return outbox_message

    async def get_pending_batch(
        self,
        batch_size: int,
    ) -> Sequence[OutboxMessage]:
        stmt = (
            select(OutboxMessage)
            .where(OutboxMessage.status == OutboxStatus.PENDING)
            .where(OutboxMessage.next_retry_at <= func.now())
            .order_by(OutboxMessage.next_retry_at)
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    def mark_sent(self, message: OutboxMessage) -> None:
        message.status = OutboxStatus.SENT
        message.sent_at = datetime.now(UTC)

    def mark_failed(self, message: OutboxMessage, error: Exception) -> None:
        message.retry_count += 1
        message.last_error = str(error)[:500]

        delay = min(
            settings.outbox_backoff_base_seconds
            * 2 ** (message.retry_count - 1),
            MAX_BACKOFF_SECONDS,
        )
        message.next_retry_at = datetime.now(UTC) + timedelta(seconds=delay)
