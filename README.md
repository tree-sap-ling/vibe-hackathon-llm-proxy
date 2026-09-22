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

Первый ответ использует **public shape-mask**, а не внутренние
`<PII:...>` tokens. Для опубликованного в задании примера:

```text
Клиент Иванов Иван Иванович, паспорт 4509 123456
→
Клиент И. И. И., паспорт 45** ****56
```

Внутренняя token-mask вместе с request-local vault используется только
для точного обратного восстановления и через `/process` наружу не выдаётся.

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
- `tps` и `token_usage` для provider-reported LLM token usage;
- safe aggregate PII metrics (`processed_requests`, latency percentiles,
  counts по PII type), без исходных значений PII;
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

На current runtime `49ebad0` полный regression suite прошёл `189/189`.
Финальный release-like `/process` benchmark дал 955.4 RPS при c4 и
992.4 RPS при c6; repeated c6 sweep дал median 933.4 RPS
(914.7–984.7). Это локальные измерения одной VirtualBox VM, поэтому
они не заявляются как гарантированный production/official SLA.
Текущий 100000-unit HTTP smoke: mask 227.753 ms, demask 28.138 ms,
exact round-trip. Подробности и методика — в `BENCHMARKS.md`.

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

Официальный конкурсный контракт уже учтён в текущем `/process` path:
paired mask/demask по `payload_id`, public shape-mask, `429` с
`Retry-After`, один HTTP worker для process-local correlation state,
safe aggregate metrics и конфигурируемая per-system PII policy.

Ограничения, которые остаются важными для интерпретации результатов:
локальные benchmarks не равны инфраструктуре организаторов; 100000
whitespace-separated units не приравниваются к tokenizer tokens;
LLM streaming с обнаруженной PII намеренно fail-closed; per-system
masking style пока не настраивается.

## Per-system PII policy

Список consumer-систем и их PII policy можно менять без правки Python-кода через
`PII_POLICIES_JSON`. Если переменная не задана, сервис сохраняет совместимые
defaults: `autocheck` и `llm-proxy`, все `PiiType`, `demask_enabled=true`,
`enabled=true`.

Пример:

```bash
export PII_POLICIES_JSON='[{"system_id":"autocheck","enabled_types":["*"],"demask_enabled":true,"enabled":true},{"system_id":"llm-proxy","enabled_types":["email","phone"],"demask_enabled":false,"enabled":true}]'
```

`enabled_types` принимает значения `PiiType` из кода (`email`, `phone`,
`passport_rf`, `fio` и другие) либо одиночный wildcard `"*"`. Поля
`demask_enabled` и `enabled` — JSON boolean. Неизвестные PII types, лишние поля,
дубликаты `system_id` и неверные типы приводят к fail-fast ошибке при старте,
чтобы опечатка в security policy не включала более широкие права молча.

Текущая policy управляет списком детектируемых PII types, разрешением consumer
и demasking. Стиль маскирования пока общий для типа PII и не настраивается
per-system; это отдельное расширение roadmap.

## TPS (tokens per second)

`GET /stats` публикует поле `tps`. Оно считается только по успешным non-stream
LLM-ответам, где provider вернул `usage.total_tokens`:
`sum(provider_reported_total_tokens) / sum(proxy_observed_request_seconds)`.
Сервис не оценивает число токенов по символам или словам; если provider не прислал
`usage.total_tokens`, такой ответ в TPS не включается. `token_usage.samples`,
`provider_reported_total_tokens` и `observed_seconds` позволяют проверить базу
расчёта. Streaming TPS пока не собирается; mock provider использует фиксированный
demo `usage` только для проверки механизма метрики.
