# Архитектура LLM Proxy

## Назначение

Проект создаёт минимальный, но отказоустойчивый фундамент
высоконагруженного LLM proxy.

Основные цели:

- низкая дополнительная latency;
- контролируемое поведение при перегрузке;
- отказоустойчивость upstream provider;
- безопасный streaming;
- возможность горизонтального масштабирования;
- отсутствие лишних компонентов в hot path;
- быстрая адаптация под официальный контракт хакатона.

## Текущая архитектура

```text
                         +-------------------+
                         |      Client       |
                         +---------+---------+
                                   |
                                   v
                         +-------------------+
                         |   FastAPI Proxy   |
                         +---------+---------+
                                   |
                    +--------------+--------------+
                    |                             |
                    v                             v
          +------------------+          +------------------+
          | Concurrency Gate |          | Runtime Metrics  |
          +------------------+          +------------------+
                    |
                    v
          +--------------------+
          | Provider Routing   |
          +---------+----------+
                    |
           +--------+--------+
           |                 |
           v                 v
    +-------------+    +-------------+
    |   Primary   |    |  Fallback   |
    |   Provider  |    |   Provider  |
    +-------------+    +-------------+
```

Оба provider имеют независимые circuit breaker.

## Обычный запрос

```text
Client request
      |
      v
Concurrency Gate
      |
      +--> limit exceeded -> HTTP 503
      |
      v
Routing deadline
      |
      v
Primary provider
      |
      +--> success / 4xx -> return response
      |
      +--> network error / timeout / 5xx
                    |
                    v
              Fallback provider
                    |
                    v
               Client response
```

`4xx` не вызывает fallback, потому что обычно означает ошибку клиентского
запроса, а не сбой provider.

## Streaming request path

До первого chunk:

```text
primary send()
      |
      +--> connection error
      |         |
      |         v
      |      fallback
      |
      v
HTTP response
      |
      v
wait first chunk
      |
      +--> read error / timeout
      |         |
      |         v
      |      fallback
      |
      v
first chunk received
```

После первого chunk:

```text
first chunk
    |
    v
client started receiving response
    |
    v
provider is fixed
    |
    +--> later stream error
              |
              v
      record failure and finish stream
```

После начала клиентского stream автоматическое переключение provider
запрещено. Иначе клиент мог бы получить начало ответа от Provider A
и продолжение ответа от Provider B.

## Routing time budget

Один клиентский запрос не должен получать отдельный полный timeout
на каждого provider.

Используется общий deadline:

```text
ROUTING_TIMEOUT_SECONDS = 5

0s                         5s
|---------------------------|
      primary
|------------|
             fallback
             |-------------|
```

Fallback получает только оставшуюся часть общего budget.

Для non-stream запросов budget действует до получения upstream response.
Для streaming запросов budget действует до первого chunk.

После первого chunk routing завершён, поэтому дальнейшая длительность
LLM generation этим deadline не ограничивается.

## Bounded concurrency

Proxy не создаёт бесконечную внутреннюю очередь.

`MAX_IN_FLIGHT` задаёт максимальное число запросов в обработке.

Если все слоты заняты, новый запрос быстро получает
`HTTP 503 Proxy overloaded`.

Это позволяет сбрасывать перегрузку вместо роста latency, памяти
и количества ожидающих coroutine.

## Circuit breaker

Для каждого provider создаётся независимый circuit breaker.

```text
             failures >= threshold
closed -----------------------------> open
  ^                                    |
  |                                    |
  | success                            | recovery timeout
  |                                    v
  +------------------------------- half_open
```

Основные параметры:

```text
CIRCUIT_FAILURE_THRESHOLD
CIRCUIT_RECOVERY_TIMEOUT_SECONDS
```

Это позволяет перестать отправлять запросы к явно неработающему provider
и не тратить routing budget на заведомо неуспешные попытки.

## Provider runtime

Runtime-состояние provider:

```text
ProviderRuntime
    |
    +--> ProviderConfig
    |
    +--> CircuitBreaker
```

Primary и fallback не разделяют circuit state.

## HTTP client

В lifespan приложения создаётся один общий `httpx.AsyncClient`.

Он переиспользуется между запросами, что позволяет переиспользовать
HTTP connections вместо создания нового client на каждый LLM request.

## Health checks

### `/healthz`

Проверяет только жизнь самого proxy и не зависит от upstream.

### `/readyz`

Проверяет настроенные upstream provider.

Proxy считается ready, если доступен хотя бы один provider.
Это позволяет продолжать принимать трафик при отказе primary,
если fallback остаётся работоспособным.

## Метрики

`GET /stats` публикует локальное runtime-состояние процесса.

Основные метрики:

```text
in_flight
max_in_flight
total_requests
completed_requests
overload_rejections
circuit_open_rejections
upstream_errors
upstream_timeouts
```

Также публикуются отдельные circuit snapshots:

```text
providers.primary.circuit
providers.fallback.circuit
```

Метрики сейчас process-local.

## Масштабирование

Proxy старается оставаться stateless относительно пользовательских данных.

Базовый вариант горизонтального масштабирования:

```text
                   +----------------+
Clients ---------->| Load Balancer  |
                   +--------+-------+
                            |
             +--------------+--------------+
             |              |              |
             v              v              v
        +---------+     +---------+     +---------+
        | Proxy 1 |     | Proxy 2 |     | Proxy 3 |
        +----+----+     +----+----+     +----+----+
             |               |               |
             +---------------+---------------+
                             |
                             v
                     LLM Providers
```

Текущие concurrency counters, statistics и circuit breaker state
локальны для каждой replica.

Shared state стоит добавлять только если официальный контракт требует,
например:

- глобальный rate limit;
- общий circuit state;
- распределённую очередь;
- глобальные quotas.

В таком случае может быть оправдан Redis.

## Docker

Production image основан на `python:3.12-slim`.

В image не копируются:

```text
.git
.venv
.env
tests
scripts
mock_provider
```

Процесс запускается от непривилегированного пользователя `app`.

Проверен запуск proxy и mock-provider в отдельных контейнерах
через отдельную Docker network.

Проверены:

- Docker DNS;
- readiness через fallback;
- обычный completion через fallback;
- streaming completion через fallback;
- per-provider circuit metrics.

## Безопасность

Основные правила:

- реальные API keys не хранятся в Git;
- `.env` игнорируется;
- `.env.example` содержит только шаблон;
- credentials передаются через environment;
- container не запускается от root;
- debug/test artifacts не входят в production image.

## Нагрузочное поведение

Локальные benchmark-результаты находятся в `BENCHMARKS.md`.

Проект измеряет:

- throughput;
- success rate;
- rejection rate;
- p50;
- p95;
- p99;
- streaming TTFT.

Локальные benchmark нельзя напрямую интерпретировать как production SLA.
Они нужны для проверки поведения архитектуры и регрессий.

## Что намеренно не находится в hot path

Без требования задачи не добавляются:

- Kubernetes;
- Kafka;
- PostgreSQL;
- vector database;
- agent framework;
- semantic cache;
- LLM router.

Каждый дополнительный компонент увеличивает latency, число failure mode
и время, необходимое для адаптации решения на хакатоне.

## Неизвестные параметры официального задания

После открытия задания нужно подтвердить:

- точный request/response contract;
- обязательные endpoint;
- startup command;
- требования к Docker или Compose;
- порт;
- internet access;
- предоставляемый LLM endpoint;
- credentials;
- SLA;
- TTFT или full-response latency;
- p95/p99 требования;
- ожидаемый RPS;
- concurrency;
- streaming requirements;
- CPU limits;
- RAM limits;
- timeout rules;
- failure scenarios;
- требования к persistence;
- требования к shared state;
- cost/token limits.

До получения этих данных архитектура не должна искусственно
усложняться предположениями.
