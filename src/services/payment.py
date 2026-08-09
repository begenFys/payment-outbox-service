import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.enums import OutboxEventType
from src.models import Payment
from src.repositories import OutboxMessageRepository, PaymentRepository
from src.schemas import (
    CreatePaymentRequest,
    PaymentNewMessage,
)


class PaymentService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.payment_repository = PaymentRepository(session)
        self.outbox_message_repository = OutboxMessageRepository(session)

    async def create_payment(
        self,
        body: CreatePaymentRequest,
        idempotency_key: str,
    ) -> Payment:
        try:
            payment = await self.payment_repository.create(
                amount=body.amount,
                currency=body.currency,
                description=body.description,
                idempotency_key=idempotency_key,
                webhook_url=str(body.webhook_url),
                extra_data=body.metadata,
            )
            outbox_message_payload = PaymentNewMessage(
                payment_id=payment.id,
            ).model_dump(mode="json")
            await self.outbox_message_repository.create(
                event_type=OutboxEventType.PAYMENT_NEW,
                payload=outbox_message_payload,
            )
            await self.session.commit()
            return payment
        except IntegrityError:
            await self.session.rollback()
            existing_payment = (
                await self.payment_repository.get_by_idempotency_key(
                    idempotency_key,
                )
            )
            if existing_payment:
                return existing_payment
            raise

    async def get_payment(self, payment_id: uuid.UUID) -> Payment | None:
        return await self.payment_repository.get_by_id(payment_id)
