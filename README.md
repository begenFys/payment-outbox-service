# Basis Payment Service

[![CI](https://github.com/begenFys/basis-payment-service/actions/workflows/ci.yml/badge.svg)](https://github.com/begenFys/basis-payment-service/actions/workflows/ci.yml)

English | [Русский](README.ru.md)

An asynchronous payment processing service. It accepts a payment over HTTP,
processes it through an emulated payment gateway and notifies the client with
a webhook.

The point of the project is the delivery guarantees around the happy path:
an idempotent API, a transactional outbox between PostgreSQL and RabbitMQ, an
idempotent consumer, and retries with a dead-letter queue. Design decisions
and failure scenarios are covered in [architecture.md](architecture.md)
(in Russian).

## Stack

FastAPI, SQLAlchemy 2.0 (async, asyncpg), PostgreSQL 18, RabbitMQ 4 via
FastStream, Alembic, Docker Compose. Dependencies are managed with uv; code is
checked with ruff and mypy in strict mode.

## Quick start

Requires Docker.

```bash
cp .env.example .env
make dc-build
make dc-up
```

This starts five services: PostgreSQL, RabbitMQ, the API, the consumer and the
outbox relay. Migrations are applied by a separate `basis-migrate` container;
the other services wait for it to finish.

- API: http://127.0.0.1:8000, Swagger UI at `/docs`
- RabbitMQ management UI: http://127.0.0.1:15672 (`admin` / `admin`)

## API

Create a payment. The idempotency key is passed in a header:

```bash
curl -X POST localhost:8000/api/v1/payment/ \
  -H "X-API-Key: your-api-key-here" \
  -H "Idempotency-Key: order-42" \
  -H "Content-Type: application/json" \
  -d '{
    "amount": "100.50",
    "currency": "RUB",
    "description": "order 42",
    "metadata": {"order_id": 42},
    "webhook_url": "https://example.com/hook"
  }'
```

The response is `202 Accepted`: the payment is queued for processing.

```json
{"id": "fe5eccbb-...", "status": "pending", "created_at": "2026-08-09T09:32:14Z"}
```

Repeating the request with the same `Idempotency-Key` returns the same payment
and the same status code; no new payment is created.

Get a payment:

```bash
curl localhost:8000/api/v1/payment/{id} -H "X-API-Key: your-api-key-here"
```

After a few seconds the status becomes `succeeded` or `failed`: the gateway
emulates a 2–5 second delay and declines 10% of payments.

The health check needs no key:

```bash
curl localhost:8000/api/v1/health/
```

## How it works

1. The API writes the payment and an outbox event **in one transaction**.
2. The relay picks up unsent events and publishes them to RabbitMQ.
3. The consumer runs the payment through the gateway, stores the result and
   sends the webhook.

External calls (the gateway and the webhook) happen outside database
transactions, so a slow third party never holds a connection or a row lock.

## Guarantees

| Guarantee | Protects against | Mechanism |
|---|---|---|
| API idempotency | Double clicks, client retries after a timeout | `UNIQUE(idempotency_key)`; insert first, on conflict roll back and return the existing payment |
| Transactional outbox | Payment saved but the event never reaches the broker | Event is written in the same transaction; the relay publishes with `FOR UPDATE SKIP LOCKED` and retries with backoff (at-least-once) |
| Consumer idempotency | Duplicate delivery, crash between commit and ack | `UPDATE ... WHERE status = 'pending' RETURNING id`; only the winner stores the result and sends the webhook |
| Retry and DLQ | Database outage, gateway error | Retry queue with TTL dead-lettering back to the main queue; attempts counted from RabbitMQ's `x-death` header, so the count survives restarts; after the limit the message goes to `payments.dlq` |

Each guarantee is covered by tests. Transaction boundaries, the queue topology
and why each choice was made are described in
[architecture.md](architecture.md).

## Tests

```bash
make test
```

Integration tests start PostgreSQL with testcontainers, so Docker must be
running. Tests that don't need a database can be run on their own:

```bash
uv run pytest -m "not integration"
```

The test database schema is built by the Alembic migrations, not
`create_all`, so every run also checks the migrations.

## Code checks

```bash
make check-all
```

Runs ruff (line length 80), mypy in strict mode and the tests. The same checks
run in pre-commit and in GitHub Actions.

## Configuration

All settings live in `.env.example`, which also holds the defaults. The ones
that change behaviour:

| Variable | Meaning |
|---|---|
| `API_KEY` | key expected in the `X-API-Key` header |
| `GATEWAY_SUCCESS_RATE` | share of successful gateway responses |
| `GATEWAY_MIN_DELAY_SECONDS`, `GATEWAY_MAX_DELAY_SECONDS` | gateway delay range |
| `OUTBOX_POLL_INTERVAL_SECONDS` | how often the relay polls the outbox |
| `OUTBOX_BACKOFF_BASE_SECONDS` | base for exponential backoff after a failed publish |
| `RABBITMQ_MESSAGE_TTL` | how long a message waits in the retry queue, ms |
| `CONSUMER_MAX_ATTEMPTS` | attempts before a message goes to the DLQ |
| `WEBHOOK_MAX_ATTEMPTS`, `WEBHOOK_TIMEOUT_SECONDS` | webhook retries and timeout |

## Known limitations

Details are at the end of [architecture.md](architecture.md). In short:

- the request body is not compared when an `Idempotency-Key` is reused;
- there is no endpoint to resend undelivered webhooks, although the data for
  it is stored;
- a single retry queue with a fixed TTL, no exponential delay;
- the outbox table is never cleaned up;
- on duplicate delivery the gateway may be called twice; the payment state is
  still correct and the webhook is sent once;
- the retry loop through a real RabbitMQ was tested manually; tests cover the
  attempt counting and the DLQ routing.
