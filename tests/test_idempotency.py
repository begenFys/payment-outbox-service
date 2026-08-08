import asyncio

from sqlalchemy import text

URL = "/api/v1/payment/"
BODY = {
    "amount": "100.50",
    "currency": "RUB",
    "description": "test",
    "webhook_url": "https://example.com/webhook",
}


async def test_repeat_with_same_key_returns_same_payment(client, session):
    headers = {"Idempotency-Key": "key-1"}

    first = await client.post(URL, json=BODY, headers=headers)
    second = await client.post(URL, json=BODY, headers=headers)

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["id"] == second.json()["id"]

    payments = (
        await session.execute(
            text("select count(*) from payments;"),
        )
    ).scalar()
    messages = (
        await session.execute(
            text("select count(*) from outbox_messages;"),
        )
    ).scalar()
    assert payments == 1
    assert messages == 1


async def test_concurrent_requests_with_same_key_create_one_payment(
    client,
    session,
):
    headers = {"Idempotency-Key": "key-1"}

    first, second = await asyncio.gather(
        client.post(URL, json=BODY, headers=headers),
        client.post(URL, json=BODY, headers=headers),
    )

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["id"] == second.json()["id"]

    payments = (
        await session.execute(
            text("select count(*) from payments;"),
        )
    ).scalar()
    messages = (
        await session.execute(
            text("select count(*) from outbox_messages;"),
        )
    ).scalar()
    assert payments == 1
    assert messages == 1
