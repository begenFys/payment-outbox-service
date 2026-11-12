# Payment Outbox Service

[![CI](https://github.com/begenFys/payment-outbox-service/actions/workflows/ci.yml/badge.svg)](https://github.com/begenFys/payment-outbox-service/actions/workflows/ci.yml)

[English](README.md) | Русский

Асинхронный сервис процессинга платежей: принимает платёж, обрабатывает его
через эмулируемый платёжный шлюз и уведомляет клиента вебхуком.

Главное в проекте — гарантии доставки вокруг основного сценария:
идемпотентный API, transactional outbox между PostgreSQL и RabbitMQ,
идемпотентный консьюмер, повторы и DLQ. Проектные решения и сценарии отказов
разобраны в [architecture.md](architecture.md).

## Стек

FastAPI, SQLAlchemy 2.0 (async, asyncpg), PostgreSQL 18, RabbitMQ 4 через
FastStream, Alembic, Docker Compose. Зависимости — uv, проверки — ruff и mypy
в strict-режиме.

## Быстрый старт

Нужен Docker.

```bash
cp .env.example .env
make dc-build
make dc-up
```

Поднимаются пять сервисов: PostgreSQL, RabbitMQ, API, консьюмер и outbox relay.
Миграции накатывает отдельный контейнер `payments-migrate`, остальные ждут его
завершения.

- API — http://127.0.0.1:8000, Swagger на `/docs`
- RabbitMQ UI — http://127.0.0.1:15672 (`admin` / `admin`)

## Примеры запросов

Создание платежа. Ключ идемпотентности передаётся заголовком:

```bash
curl -X POST localhost:8000/api/v1/payment/ \
  -H "X-API-Key: your-api-key-here" \
  -H "Idempotency-Key: order-42" \
  -H "Content-Type: application/json" \
  -d '{
    "amount": "100.50",
    "currency": "RUB",
    "description": "заказ 42",
    "metadata": {"order_id": 42},
    "webhook_url": "https://example.com/hook"
  }'
```

Ответ — `202 Accepted`, платёж принят в обработку:

```json
{"id": "fe5eccbb-...", "status": "pending", "created_at": "2026-08-09T09:32:14Z"}
```

Повторный запрос с тем же `Idempotency-Key` вернёт тот же платёж и тот же код,
нового платежа не появится.

Получение платежа:

```bash
curl localhost:8000/api/v1/payment/{id} -H "X-API-Key: your-api-key-here"
```

Через несколько секунд статус становится `succeeded` или `failed` — шлюз
эмулирует задержку 2–5 секунд и отказывает в 10% случаев.

Health-check доступен без ключа:

```bash
curl localhost:8000/api/v1/health/
```

## Как это работает

1. API пишет платёж и событие в outbox **одной транзакцией**.
2. Relay читает неотправленные события и публикует их в RabbitMQ.
3. Консьюмер обрабатывает платёж через шлюз, записывает результат и отправляет
   вебхук.

Внешние вызовы — шлюз и вебхук — выполняются вне транзакций базы, поэтому
медленный внешний сервис не держит соединение и блокировку строки.

## Гарантии

| Гарантия | От чего защищает | Как устроена |
|---|---|---|
| Идемпотентность API | Двойной клик, повтор запроса после таймаута | `UNIQUE(idempotency_key)`: сразу INSERT, при конфликте откат и возврат уже созданного платежа |
| Transactional outbox | Платёж записан, а событие в брокер не ушло | Событие пишется той же транзакцией; relay публикует через `FOR UPDATE SKIP LOCKED` и повторяет с backoff (at-least-once) |
| Идемпотентность консьюмера | Повторная доставка, падение между COMMIT и ack | `UPDATE ... WHERE status = 'pending' RETURNING id`: результат пишет и вебхук отправляет только один консьюмер |
| Retry и DLQ | Недоступна база, ошибка шлюза | Retry-очередь с TTL и dead-letter обратно в основную; попытки считаются по заголовку `x-death`, поэтому счётчик переживает рестарт; после лимита — `payments.dlq` |

Каждая гарантия покрыта тестами. Границы транзакций, схема очередей и
обоснование решений — в [architecture.md](architecture.md).

## Тесты

```bash
make test
```

Интеграционные тесты поднимают PostgreSQL через testcontainers, поэтому нужен
запущенный Docker. Быстрые тесты, которым база не нужна, гоняются отдельно:

```bash
uv run pytest -m "not integration"
```

Схема в тестовой базе создаётся миграциями, а не `create_all` — так каждый
прогон проверяет и сами миграции.

## Проверки кода

```bash
make check-all
```

Ruff (line-length 80), mypy в strict-режиме и тесты. Те же проверки выполняют
pre-commit и GitHub Actions.

## Переменные окружения

Все настройки — в `.env.example`, оттуда же берутся значения по умолчанию.
Значимые для поведения:

| Переменная | Смысл |
|---|---|
| `API_KEY` | ключ для заголовка `X-API-Key` |
| `GATEWAY_SUCCESS_RATE` | доля успешных ответов шлюза |
| `GATEWAY_MIN_DELAY_SECONDS`, `GATEWAY_MAX_DELAY_SECONDS` | диапазон задержки шлюза |
| `OUTBOX_POLL_INTERVAL_SECONDS` | как часто relay опрашивает outbox |
| `OUTBOX_BACKOFF_BASE_SECONDS` | база экспоненциальной задержки при неудачной публикации |
| `RABBITMQ_MESSAGE_TTL` | сколько сообщение лежит в retry-очереди, мс |
| `CONSUMER_MAX_ATTEMPTS` | после скольких попыток сообщение уходит в DLQ |
| `WEBHOOK_MAX_ATTEMPTS`, `WEBHOOK_TIMEOUT_SECONDS` | повторы и таймаут доставки вебхука |

## Сознательные ограничения

Подробно — в конце [architecture.md](architecture.md). Кратко:

- тело запроса при повторном `Idempotency-Key` не сравнивается;
- нет ручки повторной отправки недоставленных вебхуков, хотя данные для неё есть;
- retry-очередь одна, TTL фиксированный, без экспоненциальной задержки;
- outbox-таблица не чистится;
- при дублирующей доставке шлюз может быть вызван дважды — состояние платежа
  при этом не портится;
- цикл retry через реальный RabbitMQ проверен вручную, тестами покрыта логика
  подсчёта попыток и отправки в DLQ.
