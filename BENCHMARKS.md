# Benchmarks

Все результаты ниже — локальные измерения в Ubuntu 24.04 VirtualBox VM.

Клиент нагрузки и сервер в большинстве тестов работали на одной VM, поэтому
цифры включают scheduler, event loop, HTTP stack и contention за CPU.
Они полезны для regression/diagnostics, но не являются production SLA
и не доказывают достижение официального RPS 1000 на внешнем deployment.

## `/process`: current release paired benchmark

Current release candidate — `9ee854b`. Release-like `/process` performance figures below were measured on full-mask runtime `9b7b37f` and retain that historical provenance.
Benchmark выполнялся на working tree с этим exact patch непосредственно перед
commit; после измерения код patch не менялся. Собирался обычный `Dockerfile`,
container запускался default CMD с одним Uvicorn worker; client и server
работали на одной Ubuntu 24.04 VirtualBox VM.

Каждый round использовал 1500 пар mask → demask, то есть 3000 HTTP requests.
Для каждой пары проверялись exact full-hide public mask, exact demask и
`HTTP 200` на обоих запросах. Перед измерениями выполнен warmup из 40 пар.
Container logs не содержали проверяемые raw PII или внутренние `<PII:...>`
tokens.

### Default Docker CMD

```text
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

| Concurrency | Round | HTTP RPS | MASK p50 | MASK p95 | MASK p99 | DEMASK p50 | DEMASK p95 | DEMASK p99 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 4 | 1 | 907.4 | 4.106 ms | 6.538 ms | 9.603 ms | 3.834 ms | 6.073 ms | 7.859 ms |
| 4 | 2 | 935.2 | 3.976 ms | 6.192 ms | 8.464 ms | 3.821 ms | 6.012 ms | 7.514 ms |
| 4 | 3 | 988.9 | 3.808 ms | 5.864 ms | 7.011 ms | 3.630 ms | 5.464 ms | 6.296 ms |
| 6 | 1 | 1019.1 | 5.323 ms | 10.527 ms | 15.071 ms | 4.789 ms | 9.224 ms | 12.998 ms |
| 6 | 2 | 992.8 | 5.445 ms | 11.047 ms | 16.142 ms | 4.803 ms | 9.538 ms | 13.958 ms |
| 6 | 3 | 1040.4 | 5.342 ms | 10.300 ms | 15.079 ms | 4.568 ms | 8.465 ms | 12.193 ms |

Summary:

| Concurrency | Median RPS | Min RPS | Max RPS | Worst MASK p95 | Worst DEMASK p95 |
|---:|---:|---:|---:|---:|---:|
| 4 | 935.2 | 907.4 | 988.9 | 6.538 ms | 6.073 ms |
| 6 | 1019.1 | 992.8 | 1040.4 | 11.047 ms | 9.538 ms |

На c6 median пересёк ориентир 1000 HTTP RPS, но один из трёх round был
992.8 RPS, поэтому результат не формулируется как гарантированные или
стабильные >1000 RPS. Все измеренные p95/p99 остаются существенно ниже
ориентира 1 s.

Это локальный release-like regression benchmark, а не гарантия official или
production SLA на другой инфраструктуре.

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

На exact full-mask patch, затем закоммиченном как `9b7b37f`, отдельный HTTP
smoke использовал synthetic payload ровно из `100000 whitespace-separated
units`, с тестовым email в последнем unit.

Результат:

| Метрика | Значение |
|---|---:|
| Whitespace-separated units | 100000 |
| Characters | 600017 |
| UTF-8 bytes | 1100012 |
| Mask HTTP status | 200 |
| Mask latency | 180.093 ms |
| Demask HTTP status | 200 |
| Demask latency | 10.716 ms |
| Raw test email in masked result | no |
| Exact round-trip | yes |

Container logs не содержали тестовый raw email или внутренние `<PII:...>` tokens.

Важно: `100000 whitespace-separated units` — это не доказанные
`100000 tokenizer tokens`, потому что официальный tokenizer для `/process`
не задан.

## Local quality regression corpora

Локальные curated checks после tightening contextual detectors
и public-mask integration:

- synthetic corpus: 34/34;
- adversarial corpus: 53/53;
- exact-span corpus: 30/30;
- historical full regression suite на `9b7b37f`: 193/193;
- current release candidate `9ee854b`: 196/196.

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
