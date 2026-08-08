import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    DateTime,
    Enum,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base
from src.enums import Currency, OutboxEventType, OutboxStatus, PaymentStatus


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=2),
    )
    currency: Mapped[Currency] = mapped_column(
        Enum(
            Currency,
            name="currency_enum",
            values_callable=lambda e: [m.value for m in e],
        ),
    )
    description: Mapped[str] = mapped_column(
        Text,
    )
    extra_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
    )
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(
            PaymentStatus,
            name="payment_status_enum",
            values_callable=lambda e: [m.value for m in e],
        ),
        default=PaymentStatus.PENDING,
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(255),
        unique=True,
    )
    webhook_url: Mapped[str] = mapped_column(
        Text,
    )
    webhook_attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )
    webhook_last_error: Mapped[str | None] = mapped_column(
        Text,
        default=None,
    )
    webhook_delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=None,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )


class OutboxMessage(Base):
    __tablename__ = "outbox_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
    )
    event_type: Mapped[OutboxEventType] = mapped_column(
        Enum(
            OutboxEventType,
            name="outbox_event_type_enum",
            values_callable=lambda e: [m.value for m in e],
        ),
    )
    status: Mapped[OutboxStatus] = mapped_column(
        Enum(
            OutboxStatus,
            name="outbox_status_enum",
            values_callable=lambda e: [m.value for m in e],
        ),
        default=OutboxStatus.PENDING,
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )
    last_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    next_retry_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    __table_args__ = (
        Index(
            "ix_outbox_messages_status_next_retry_at",
            "status",
            "next_retry_at",
        ),
    )
