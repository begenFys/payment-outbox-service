import uuid

import pytest

from tests.constants import HEALTH_URL, PAYMENT_URL


async def test_create_without_api_key_returns_401(
    anonymous_client,
    payment_body,
    headers,
):
    response = await anonymous_client.post(
        PAYMENT_URL,
        json=payment_body,
        headers=headers,
    )

    assert response.status_code == 401


async def test_create_with_wrong_api_key_returns_401(
    anonymous_client,
    payment_body,
    headers,
):
    response = await anonymous_client.post(
        PAYMENT_URL,
        json=payment_body,
        headers=headers,
    )

    assert response.status_code == 401


async def test_healthcheck_available_without_api_key(anonymous_client):
    response = await anonymous_client.get(HEALTH_URL)
    assert response.status_code == 200


@pytest.mark.parametrize(
    "patch",
    [
        pytest.param({"amount": "0"}, id="zero_amount"),
        pytest.param({"amount": "-100.50"}, id="negative_amount"),
        pytest.param({"amount": "10.505"}, id="three_decimal_places"),
        pytest.param({"currency": "BYN"}, id="unknown_currency"),
        pytest.param({"webhook_url": "не-урл"}, id="invalid_webhook_url"),
        pytest.param({"description": ""}, id="empty_description"),
    ],
)
async def test_invalid_body_returns_422(client, payment_body, patch, headers):
    response = await client.post(
        PAYMENT_URL,
        json=payment_body | patch,
        headers=headers,
    )
    assert response.status_code == 422


async def test_get_returns_payment_with_metadata_field(
    client,
    payment_body,
    headers,
):
    response = await client.post(
        PAYMENT_URL,
        json=payment_body | {"metadata": {"order": 1}},
        headers=headers,
    )
    assert response.status_code == 202
    payment_id = response.json()["id"]
    response = await client.get(f"{PAYMENT_URL}{payment_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == payment_id
    assert body["metadata"] == {"order": 1}


async def test_get_unknown_id_returns_404(client):
    response = await client.get(f"{PAYMENT_URL}{uuid.uuid4()}")
    assert response.status_code == 404


async def test_get_invalid_uuid_returns_422(client):
    response = await client.get(f"{PAYMENT_URL}просто_строка")
    assert response.status_code == 422
