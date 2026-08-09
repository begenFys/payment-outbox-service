import asyncio

from sqlalchemy import text

from tests.constants import PAYMENT_URL


async def test_repeat_with_same_key_returns_same_payment(
    client,
    session,
    payment_body,
    headers,
):
    first = await client.post(PAYMENT_URL, json=payment_body, headers=headers)
    second = await client.post(PAYMENT_URL, json=payment_body, headers=headers)

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
    payment_body,
    headers,
):
    first, second = await asyncio.gather(
        client.post(PAYMENT_URL, json=payment_body, headers=headers),
        client.post(PAYMENT_URL, json=payment_body, headers=headers),
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
