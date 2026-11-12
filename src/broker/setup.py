from faststream.rabbit import (
    Channel,
    ExchangeType,
    RabbitBroker,
    RabbitExchange,
    RabbitQueue,
)

from src.settings import settings

RABBIT_BROKER: RabbitBroker = RabbitBroker(
    url=settings.rabbitmq_url,
    default_channel=Channel(
        prefetch_count=settings.rabbitmq_prefetch_count,
        publisher_confirms=True,
        on_return_raises=True,
    ),
)

PAYMENTS_DIRECT = RabbitExchange(
    name="payments.direct",
    type=ExchangeType.DIRECT,
    durable=True,
    auto_delete=False,
)

PAYMENT_NEW_NAME = "payments.new"
PAYMENT_RETRY_NAME = "payments.retry"
PAYMENT_DLQ_NAME = "payments.dlq"

PAYMENT_NEW_QUEUE = RabbitQueue(
    name=PAYMENT_NEW_NAME,
    durable=True,
    arguments={
        "x-dead-letter-exchange": PAYMENTS_DIRECT.name,
        "x-dead-letter-routing-key": PAYMENT_RETRY_NAME,
    },
)

PAYMENT_RETRY_QUEUE = RabbitQueue(
    name=PAYMENT_RETRY_NAME,
    durable=True,
    arguments={
        "x-message-ttl": settings.rabbitmq_message_ttl,
        "x-dead-letter-exchange": PAYMENTS_DIRECT.name,
        "x-dead-letter-routing-key": PAYMENT_NEW_NAME,
    },
)

PAYMENT_DLQ_QUEUE = RabbitQueue(
    name=PAYMENT_DLQ_NAME,
    durable=True,
)

QUEUES = (PAYMENT_NEW_QUEUE, PAYMENT_RETRY_QUEUE, PAYMENT_DLQ_QUEUE)


async def declare_topology(broker: RabbitBroker) -> None:
    exchange = await broker.declare_exchange(PAYMENTS_DIRECT)
    for queue in QUEUES:
        declared_queue = await broker.declare_queue(queue)
        await declared_queue.bind(exchange, routing_key=queue.name)
