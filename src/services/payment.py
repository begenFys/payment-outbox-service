import uuid

from loguru import logger
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.enums import OutboxEventType, PaymentStatus
from src.models import Payment
from src.repositories import OutboxMessageRepository, PaymentRepository
from src.schemas import (
    CreatePaymentRequest,
    PaymentNewMessage,
)
from src.services.gateway import PaymentGateway


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


async def process_payment(
    payment_id: uuid.UUID,
    gateway: PaymentGateway,
    session_maker: async_sessionmaker[AsyncSession],
) -> PaymentStatus | None:
    async with session_maker() as session:
        payment = await PaymentRepository(session).get_by_id(payment_id)

    if payment is None:
        logger.warning(f"Платёж {payment_id} не найден")
        return None

    if payment.status is not PaymentStatus.PENDING:
        logger.info(f"Платёж {payment_id} уже обработан, пропускаю")
        return None

    status = await gateway.process(payment.amount, payment.currency)

    async with session_maker() as session:
        processed_id = await PaymentRepository(session).mark_processed(
            payment_id,
            status,
        )
        await session.commit()

    if processed_id is None:
        logger.info(f"Платёж {payment_id} обработал другой консьюмер")
        return None

    logger.info(f"Платёж {payment_id} обработан: {status}")
    return status
