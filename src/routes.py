import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.dependencies import get_session, require_api_key
from src.schemas import (
    CreatePaymentRequest,
    CreatePaymentResponse,
    PaymentDetailResponse,
)
from src.services.payment import PaymentService

api_router = APIRouter(prefix="/api/v1")
payment_router = APIRouter(
    prefix="/payment",
    tags=["Payment"],
    dependencies=[Depends(require_api_key)],
)
health_router = APIRouter(prefix="/health")


@health_router.get("/")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@payment_router.post(
    "/",
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_payment(
    body: CreatePaymentRequest,
    idempotency_key: Annotated[
        str,
        Header(..., alias="Idempotency-Key", min_length=1, max_length=255),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CreatePaymentResponse:
    service = PaymentService(session)
    return CreatePaymentResponse.model_validate(
        await service.create_payment(body, idempotency_key),
    )


@payment_router.get(
    "/{payment_id}",
    status_code=status.HTTP_200_OK,
)
async def get_payment(
    payment_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PaymentDetailResponse:
    service = PaymentService(session)
    payment = await service.get_payment(payment_id)
    if payment:
        return PaymentDetailResponse.model_validate(payment)
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


api_router.include_router(payment_router)
api_router.include_router(health_router)

__all__ = ["api_router"]
