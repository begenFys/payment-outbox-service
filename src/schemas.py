import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from src.enums import Currency, PaymentStatus


class CreatePaymentRequest(BaseModel):
    amount: Decimal = Field(
        ...,
        gt=0,
        max_digits=12,
        decimal_places=2,
    )
    currency: Currency
    description: str = Field(
        ...,
        min_length=1,
        max_length=500,
    )
    metadata: dict[str, Any] | None = Field(None)
    webhook_url: HttpUrl


class CreatePaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: PaymentStatus
    created_at: datetime


class PaymentDetailResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )

    id: uuid.UUID
    amount: Decimal
    currency: Currency
    description: str
    metadata: dict[str, Any] | None = Field(
        None,
        validation_alias="extra_data",
    )
    status: PaymentStatus
    idempotency_key: str
    webhook_url: str
    created_at: datetime
    processed_at: datetime | None = Field(None)


class PaymentNewMessage(BaseModel):
    payment_id: uuid.UUID


class WebhookPayload(BaseModel):
    payment_id: uuid.UUID
    status: PaymentStatus
    amount: Decimal
    currency: Currency
