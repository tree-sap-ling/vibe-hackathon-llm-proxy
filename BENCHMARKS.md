# Benchmarks

Все результаты ниже — локальные измерения в Ubuntu 24.04 VirtualBox VM.

Клиент нагрузки и сервер в большинстве тестов работали на одной VM, поэтому
цифры включают scheduler, event loop, HTTP stack и contention за CPU.
Они полезны для regression/diagnostics, но не являются production SLA
и не доказывают достижение официального RPS 1000 на внешнем deployment.

## `/process`: current release paired benchmark

Последний benchmark выполнен после интеграции public shape-mask,
на committed runtime `e85532a`.

Во всех прогонах:

- один Uvicorn worker;
- `PROCESS_MAX_IN_FLIGHT=50`;
- 2000 пар mask → demask;
- 4000 HTTP requests на точку;
- exact round-trip check для каждой пары;
- public response проверялся на отсутствие `<PII:...>`;
- synthetic payload содержал email;
- client и server работали на одной VirtualBox VM.

### Docker CMD, access log включён

Это режим, который реально запускается текущим `Dockerfile`:

```text
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

| Client concurrency | Successful pairs | HTTP 200 | Successful HTTP RPS | MASK p50 | MASK p95 | DEMASK p50 | DEMASK p95 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 4 | 2000/2000 | 4000/4000 | 1074.4 | 3.49 ms | 5.52 ms | 3.36 ms | 5.41 ms |
| 6 | 2000/2000 | 4000/4000 | 1094.8 | 4.83 ms | 9.57 ms | 4.79 ms | 9.44 ms |

Для каждой точки container logs содержали 4000 access-log строк и
2000 safe PII audit events. Проверки не обнаружили raw email,
`payload_id` или внутренних `<PII:...>` tokens в логах.

Эти результаты показывают, что текущая release-конфигурация на этой
локальной VM пересекла ориентир 1000 successful HTTP req/s. Это не
является доказательством official SLA на инфраструктуре организаторов.

### Локальный uvicorn с `--no-access-log`

Контрольный прогон того же committed runtime без access log:

| Client concurrency | Successful pairs | Successful HTTP RPS | MASK p50 | MASK p95 | DEMASK p50 | DEMASK p95 |
|---:|---:|---:|---:|---:|---:|---:|
| 4 | 2000/2000 | 1219.8 | 2.99 ms | 5.32 ms | 2.96 ms | 5.05 ms |
| 6 | 2000/2000 | 1299.4 | 3.69 ms | 8.68 ms | 3.62 ms | 8.51 ms |

Access logging поэтому измеримо влияет на throughput, но в текущем
Docker CMD он оставлен включённым: даже с ним локальный release-run
прошёл без ошибок и выше 1000 req/s. Runtime специально не менялся
после этого измерения.

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

Post-public-mask HTTP smoke использовал synthetic payload ровно из:

```text
100000 whitespace-separated units
600011 bytes
```

Это были `99998` слов `token`, затем `Email:` и
`user@example.com`.

Результат:

| Метрика | Значение |
|---|---:|
| Mask HTTP status | 200 |
| Mask latency | 248.85 ms |
| Demask HTTP status | 200 |
| Demask latency | 9.21 ms |
| Public email mask present | yes |
| Internal `<PII:...>` in public response | no |
| Exact round-trip | yes |

Server logs не содержали raw email, `payload_id` или внутренних
`<PII:...>` tokens.

Этот payload отличается от более раннего synthetic large-text smoke,
поэтому отдельные latency numbers нельзя трактовать как точное
before/after сравнение renderer-а.

Важно: `100000 whitespace-separated units` — это не доказанные
`100000 tokenizer tokens`, потому что официальный tokenizer не задан.

## Local quality regression corpora

Локальные curated checks после tightening contextual detectors
и public-mask integration:

- synthetic corpus: 34/34;
- adversarial corpus: 53/53;
- exact-span corpus: 30/30;
- полный regression suite после интеграции: 167/167.

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
