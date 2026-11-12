from faststream.rabbit import RabbitBroker
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from src.broker.setup import PAYMENTS_DIRECT
from src.repositories import OutboxMessageRepository
from src.settings import settings


async def publish_pending_messages(
    session: AsyncSession,
    broker: RabbitBroker,
) -> int:
    repository = OutboxMessageRepository(session)
    messages = await repository.get_pending_batch(settings.outbox_batch_size)
    for message in messages:
        try:
            await broker.publish(
                message.payload,
                routing_key=message.event_type,
                exchange=PAYMENTS_DIRECT,
                persist=True,
                mandatory=True,
            )
        # Ошибка одной записи не должна останавливать relay: помечаем её
        # неудачной, следующий проход возьмёт её снова.
        except Exception as exc:
            logger.warning(
                "Не удалось опубликовать сообщение {}: {}",
                message.id,
                exc,
            )
            repository.mark_failed(message, exc)
        else:
            repository.mark_sent(message)
    await session.commit()
    return len(messages)
