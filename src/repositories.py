import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.enums import Currency, OutboxEventType
from src.models import OutboxMessage, Payment


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
