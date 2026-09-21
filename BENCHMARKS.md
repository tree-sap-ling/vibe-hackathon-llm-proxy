# Benchmarks

Все результаты ниже — локальные измерения в Ubuntu 24.04 VirtualBox VM.

Клиент нагрузки и сервер в большинстве тестов работали на одной VM, поэтому
цифры включают scheduler, event loop, HTTP stack и contention за CPU.
Они полезны для regression/diagnostics, но не являются production SLA
и не доказывают достижение официального RPS 1000 на внешнем deployment.

## `/process`: sustained paired benchmark

Последний benchmark после добавления official contract, correlation TTL,
safe audit logging и overload protection.

Конфигурация:

- один Uvicorn worker;
- `PROCESS_MAX_IN_FLIGHT=50`;
- 2000 пар mask → demask;
- exact round-trip check для каждой пары;
- до 3 HTTP attempts при `429`;
- synthetic payload содержит ФИО, email, телефон и паспорт.

### Concurrency 25

| Метрика | MASK | DEMASK |
|---|---:|---:|
| Successful requests | 2000 | 2000 |
| 429 attempts | 0 | 0 |
| p50 | 34.63 ms | 23.40 ms |
| p95 | 126.64 ms | 117.17 ms |
| p99 | 204.65 ms | 191.94 ms |
| max | 338.84 ms | 328.17 ms |

Итог:

- 2000/2000 successful pairs;
- 0 pair failures;
- successful HTTP throughput: 570.3 req/s;
- PII core p95: 0.156 ms;
- safe log check: без raw PII и masking tokens.

### Concurrency 50

| Метрика | MASK | DEMASK |
|---|---:|---:|
| Successful requests | 2000 | 2000 |
| 429 attempts | 0 | 0 |
| p50 | 59.15 ms | 65.43 ms |
| p95 | 340.51 ms | 347.26 ms |
| p99 | 584.93 ms | 648.40 ms |
| max | 1059.62 ms | 1180.40 ms |

Итог:

- 2000/2000 successful pairs;
- 0 pair failures;
- successful HTTP throughput: 472.1 req/s;
- PII core p95: 0.154 ms;
- safe log check: без raw PII и masking tokens.

Снижение throughput при большей concurrency в этой VM показывает, что
локальный client/server contention заметно влияет на результат.

## `/process`: overload behavior

Docker smoke с:

```text
PROCESS_MAX_IN_FLIGHT=1
requests=100
concurrency=100
```

Результат:

```text
HTTP 200: 42
HTTP 429: 58
Retry-After=1: 58/58
```

Это подтверждает, что application-level overload gate реально отдаёт
официально допустимый `429` с корректным `Retry-After`.

Отдельные burst-тесты с concurrency 200 показали, что endpoint-level gate
не контролирует задержку запросов, которые ещё не были запланированы
сервером в handler. Поэтому такие burst-результаты нельзя интерпретировать
как чистую latency самого PII processor.

## Large payload smoke

Docker test использовал synthetic payload:

```text
100000 whitespace-separated word-like units
600147 bytes
0.572 MiB
```

PII были размещены в начале, середине и конце текста.

Результат:

| Метрика | Значение |
|---|---:|
| Mask HTTP status | 200 |
| Mask latency | 205.88 ms |
| Demask HTTP status | 200 |
| Demask latency | 14.90 ms |
| PII processor time | 185.043 ms |
| Detected entities | 4 |
| Exact round-trip | yes |
| Raw expected PII left in mask | none |

Safe Docker logs не содержали raw email, `payload_id` или `<PII:...>` tokens.

Важно: `100000 whitespace-separated units` — это не доказанные
`100000 tokenizer tokens`, потому что официальный tokenizer не задан.

## Local quality regression corpora

Локальные curated checks после tightening contextual detectors:

- synthetic corpus: 34/34;
- adversarial corpus: 53/53.

Эти цифры означают только прохождение наших собственных cases.
Они не являются официальным quality score и не подтверждают target 95%
на скрытом датасете организаторов.

## Historical LLM proxy baseline

До публикации официального `/process` был измерен базовый LLM proxy
с deterministic mock provider.

Конфигурация:

- 20 requests per run;
- mock upstream delay: 1000 ms;
- concurrency совпадала с `MAX_IN_FLIGHT`;
- proxy и mock provider работали на одной VM.

| MAX_IN_FLIGHT | Successful req/s | Success rate | p50 ms | p95 ms | p99 ms |
|---:|---:|---:|---:|---:|---:|
| 1 | 0.98 | 100% | 1013.6 | 1023.3 | 1049.7 |
| 2 | 1.96 | 100% | 1016.0 | 1036.0 | 1058.6 |
| 4 | 3.88 | 100% | 1020.9 | 1053.4 | 1077.7 |

Этот benchmark относится к `/v1/chat/completions` и не описывает
производительность официального `/process`.

## Historical streaming TTFT

Local end-to-end streaming measurements:

| Mock first-chunk delay | Measured TTFT | TTFT difference | Measured total time |
|---:|---:|---:|---:|
| 500 ms | 579.2 ms | +79.2 ms | 1795.2 ms |
| 1000 ms | 1080.6 ms | +80.6 ms | 2289.5 ms |
| 2000 ms | 2085.4 ms | +85.4 ms | 3290.8 ms |

Direct-vs-proxy paired measurements:

| Run | Direct TTFT | Proxy TTFT | Difference |
|---:|---:|---:|---:|
| 1 | 574.6 ms | 583.3 ms | +8.7 ms |
| 2 | 581.9 ms | 575.8 ms | -6.1 ms |
| 3 | 569.7 ms | 574.5 ms | +4.8 ms |
| 4 | 570.7 ms | 572.6 ms | +1.9 ms |

Average direct TTFT: 574.2 ms.

Average proxy TTFT: 576.6 ms.

Average paired difference: +2.3 ms.

Median paired difference: +3.4 ms.

Эти streaming measurements относятся только к retained LLM proxy subsystem.
