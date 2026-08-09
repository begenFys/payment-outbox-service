from enum import StrEnum


class OutboxStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"


class OutboxEventType(StrEnum):
    PAYMENT_NEW = "payments.new"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class Currency(StrEnum):
    RUB = "RUB"
    USD = "USD"
    EUR = "EUR"
