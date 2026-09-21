# Vibe Hackathon — PII Protection Service

Сервис для обнаружения, маскирования и обратного восстановления
персональных данных по официальному контракту хакатона.

Основной конкурсный endpoint — `POST /process`.
Первый запрос с новым `payload_id` маскирует строку и сохраняет
корреляцию, второй запрос с тем же `payload_id` восстанавливает
исходную строку.

Проект также сохраняет подготовленный ранее LLM-proxy foundation:
асинхронный routing, fallback, circuit breaker, streaming и метрики.

## Что уже реализовано

Прокси умеет:

- принимать OpenAI-подобные запросы `POST /v1/chat/completions`;
- работать асинхронно на FastAPI + httpx;
- проксировать обычные JSON-ответы;
- проксировать SSE streaming-ответы;
- ограничивать число одновременно обрабатываемых запросов;
- быстро отклонять перегрузку вместо накопления очереди;
- использовать primary и fallback LLM provider;
- хранить независимый circuit breaker для каждого provider;
- переключаться на fallback при сетевой ошибке, timeout или `5xx`;
- безопасно переключать streaming-запрос только до первого chunk;
- не смешивать ответы разных provider после начала streaming;
- применять общий routing time budget для primary + fallback;
- считать proxy ready, если доступен хотя бы один provider;
- публиковать runtime-метрики;
- работать без внешних API-ключей с локальным mock-provider;
- запускаться в Docker от непривилегированного пользователя.

## Основной request path

```text
Client
  |
  v
FastAPI proxy
  |
  +--> overload protection
  |
  +--> provider routing
          |
          +--> primary
          |
          +--> fallback
```

Для streaming действует важное правило:

```text
primary
  |
  +--> ошибка до первого chunk
  |       |
  |       v
  |    fallback разрешён
  |
  +--> первый chunk получен
          |
          v
     provider зафиксирован
          |
          +--> дальнейший fallback запрещён
```

Так proxy не может отдать клиенту начало ответа от одного provider,
а продолжение — от другого.

## Endpoint-ы

### `POST /process`

Официальный endpoint для автопроверки маскирования/демаскирования.

Request:

```json
{
  "payload": "Клиент Иванов Иван Иванович, паспорт 4509 123456",
  "payload_id": "item-1"
}
```

Response:

```json
{
  "result": "замаскированная строка"
}
```

Поведение:

- новый `payload_id`: `payload` считается исходной строкой и маскируется;
- повтор исходной строки с тем же `payload_id`: возвращается та же маска;
- ранее возвращённая маска с тем же `payload_id`: восстанавливается исходная строка;
- конфликтующее содержимое для существующего `payload_id`: `HTTP 409`;
- при перегрузке endpoint может вернуть `HTTP 429` с `Retry-After: 1`.

Корреляционное состояние хранится в памяти процесса, поэтому конкурсный
`/process` запускается одним HTTP worker.

### `POST /v1/chat/completions`

Основной LLM proxy endpoint.

Поддерживаются обычные ответы и streaming через `"stream": true`.

### `GET /healthz`

Liveness самого proxy. Не зависит от состояния upstream provider.

Пример:

```json
{"status":"ok"}
```

### `GET /readyz`

Readiness proxy. Proxy считается готовым, если доступен хотя бы один
настроенный provider.

### `GET /stats`

Runtime-метрики текущего процесса:

- `in_flight`;
- `max_in_flight`;
- `total_requests`;
- `completed_requests`;
- `overload_rejections`;
- `circuit_open_rejections`;
- `upstream_errors`;
- `upstream_timeouts`;
- отдельные circuit breaker metrics для primary и fallback.

## Локальный запуск

Создание окружения:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Терминал 1 — mock-provider:

```bash
source .venv/bin/activate
python -m uvicorn mock_provider.main:app \
  --host 127.0.0.1 \
  --port 9000
```

Терминал 2 — proxy:

```bash
source .venv/bin/activate
python -m uvicorn app.main:app \
  --host 127.0.0.1 \
  --port 8000
```

Проверка:

```bash
curl -i http://127.0.0.1:8000/healthz
curl -i http://127.0.0.1:8000/readyz
```

Обычный запрос:

```bash
curl -s \
  -X POST http://127.0.0.1:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model":"mock-model",
    "messages":[
      {
        "role":"user",
        "content":"hello"
      }
    ]
  }'
```

Streaming:

```bash
curl -N \
  -X POST http://127.0.0.1:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model":"mock-model",
    "stream":true,
    "messages":[
      {
        "role":"user",
        "content":"hello streaming"
      }
    ]
  }'
```

## Конфигурация

Основные переменные окружения:

| Переменная | Назначение |
|---|---|
| `UPSTREAM_BASE_URL` | URL primary provider |
| `UPSTREAM_API_KEY` | API key primary provider |
| `FALLBACK_UPSTREAM_BASE_URL` | URL fallback provider |
| `FALLBACK_UPSTREAM_API_KEY` | API key fallback provider |
| `MAX_IN_FLIGHT` | Максимальное число одновременно обрабатываемых LLM proxy запросов |
| `PROCESS_MAX_IN_FLIGHT` | Лимит одновременно допущенных запросов `POST /process` |
| `ROUTING_TIMEOUT_SECONDS` | Общий time budget на выбор provider |
| `CIRCUIT_FAILURE_THRESHOLD` | Число ошибок до открытия circuit breaker |
| `CIRCUIT_RECOVERY_TIMEOUT_SECONDS` | Время до half-open probe |

Пример находится в `.env.example`.

Настоящие ключи и `.env` нельзя коммитить в Git.

## Routing time budget

`ROUTING_TIMEOUT_SECONDS` ограничивает суммарное время выбора provider.

Для обычного запроса budget действует до получения полного upstream response.

Для streaming budget действует только до первого chunk. После первого chunk
он больше не ограничивает длительность потока.

## Circuit breaker

У каждого provider отдельный circuit breaker.

```text
closed -> open -> half_open -> closed
```

После достижения порога ошибок provider временно перестаёт получать
новые попытки. После recovery timeout разрешается пробный запрос.

## Overload protection

Для LLM proxy `MAX_IN_FLIGHT` ограничивает число одновременно
обрабатываемых запросов; при переполнении используется `HTTP 503`.

Для официального `POST /process` используется отдельный
`PROCESS_MAX_IN_FLIGHT` (по умолчанию `50`). При переполнении
endpoint возвращает `HTTP 429 Too Many Requests` с `Retry-After: 1`,
что соответствует контракту автопроверки.

## Тесты

Полный набор:

```bash
python -m unittest discover -s tests -v
```

Тестами покрыты:

- обычное проксирование;
- timeout и network errors;
- overload protection;
- circuit breaker;
- primary/fallback routing;
- readiness;
- per-provider metrics;
- streaming;
- fallback до первого chunk;
- запрет fallback после первого chunk;
- общий routing time budget.

## Load testing

Локальный нагрузочный скрипт:

```bash
python scripts/load_test.py --help
```

Текущие локальные результаты находятся в `BENCHMARKS.md`.

Для streaming TTFT есть отдельный probe:

```bash
python scripts/stream_probe.py --help
```

## Быстрый запуск конкурсного `/process`

Минимальный локальный запуск в Docker:

```bash
docker build -t pii-proxy:local .
docker run --rm -p 8000:8000 pii-proxy:local
```

Проверка:

```bash
curl -X POST http://127.0.0.1:8000/process \
  -H 'Content-Type: application/json' \
  -d '{"payload":"Email: test@example.com","payload_id":"selfcheck-1"}'
```

Повторите второй запрос с тем же `payload_id`, передав в `payload`
строку `result` из первого ответа — сервис должен вернуть исходную строку.

## Качество и производительность

Локальные synthetic/adversarial тесты и benchmark-и используются для
регрессии и диагностики. Они не являются официальным score: итоговая
точность определяется скрытым эталонным датасетом организаторов.

## Docker

Сборка production image:

```bash
docker build -t llm-proxy:dev .
```

Пример запуска:

```bash
docker run --rm \
  -p 8000:8000 \
  -e UPSTREAM_BASE_URL=http://your-provider:9000 \
  llm-proxy:dev
```

Контейнер запускает proxy от непривилегированного пользователя.

Проверен отдельный Docker-network сценарий, в котором primary недоступен,
а fallback-mock находится через Docker DNS. Работают и обычные ответы,
и SSE streaming fallback.

## Что намеренно не добавлено

Пока нет оснований усложнять hot path с помощью:

- Kubernetes;
- Kafka;
- PostgreSQL;
- vector database;
- agent framework;
- semantic cache;
- LLM-based router.

Redis, load balancer и несколько proxy replica могут быть добавлены,
если этого потребует официальный контракт или сценарий нагрузки.

## Текущий статус

Фундамент уже включает:

- async request path;
- streaming;
- bounded concurrency;
- overload protection;
- circuit breaker;
- primary/fallback routing;
- safe streaming fallback;
- routing deadline;
- health/readiness;
- runtime metrics;
- automated tests;
- load tests;
- Docker image.

После публикации официального задания нужно в первую очередь уточнить:

- точный API contract;
- формат запуска для autocheck;
- обязательный порт;
- SLA и способ его измерения;
- RPS и concurrency;
- streaming requirements;
- CPU/RAM limits;
- доступность интернета;
- предоставляемые LLM endpoint и credentials;
- разрешённые внешние сервисы;
- сценарии отказов в autocheck.
