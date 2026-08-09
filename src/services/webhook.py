import asyncio
from typing import NamedTuple

import httpx
from loguru import logger

from src.models import Payment
from src.schemas import WebhookPayload
from src.settings import settings


class WebhookResult(NamedTuple):
    attempts: int
    error: str | None


class WebhookClient:
    async def deliver(self, payment: Payment) -> WebhookResult:
        payload = WebhookPayload(
            payment_id=payment.id,
            status=payment.status,
            amount=payment.amount,
            currency=payment.currency,
        ).model_dump(mode="json")

        last_error: str | None = None
        for attempt in range(1, settings.webhook_max_attempts + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=settings.webhook_timeout_seconds,
                ) as client:
                    response = await client.post(
                        payment.webhook_url,
                        json=payload,
                    )
                    response.raise_for_status()
            except Exception as exc:
                last_error = str(exc)[:500]
                logger.warning(
                    "Вебхук платежа {} не доставлен, попытка {}: {}",
                    payment.id,
                    attempt,
                    last_error,
                )
                if attempt < settings.webhook_max_attempts:
                    await asyncio.sleep(
                        settings.webhook_backoff_base_seconds * attempt,
                    )
            else:
                logger.info(
                    "Вебхук платежа {} доставлен с попытки {}",
                    payment.id,
                    attempt,
                )
                return WebhookResult(attempts=attempt, error=None)

        return WebhookResult(
            attempts=settings.webhook_max_attempts,
            error=last_error,
        )
