# Benchmarks

Все результаты ниже — локальные измерения в Ubuntu 24.04 VirtualBox VM.

Клиент нагрузки и сервер в большинстве тестов работали на одной VM, поэтому
цифры включают scheduler, event loop, HTTP stack и contention за CPU.
Они полезны для regression/diagnostics, но не являются production SLA
и не доказывают достижение официального RPS 1000 на внешнем deployment.

## `/process`: current release paired benchmark

Финальный release-like benchmark выполнен на committed runtime `49ebad0`.
Собирался текущий `Dockerfile`, контейнер запускался его обычным CMD с одним
Uvicorn worker; client и server работали на одной Ubuntu 24.04 VirtualBox VM.
Поэтому результаты подходят для локальной regression/diagnostics, но не являются
production SLA и не гарантируют ту же пропускную способность на другой
инфраструктуре.

В основном прогоне использовались 2000 пар mask → demask на точку
(4000 HTTP requests), exact check опубликованной shape-mask и exact round-trip
для каждой пары. Все запросы завершились `HTTP 200`; container logs не содержали
проверяемые raw PII или внутренние `<PII:...>` tokens.

### Default Docker CMD

```text
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

| Client concurrency | Successful pairs | HTTP 200 | HTTP RPS | MASK p50 | MASK p95 | MASK p99 | DEMASK p50 | DEMASK p95 | DEMASK p99 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 4 | 2000/2000 | 4000/4000 | 955.4 | 3.845 ms | 5.994 ms | 7.811 ms | 3.684 ms | 5.611 ms | 7.402 ms |
| 6 | 2000/2000 | 4000/4000 | 992.4 | 5.558 ms | 10.854 ms | 15.210 ms | 4.892 ms | 9.337 ms | 13.007 ms |

Ориентир 1000 HTTP RPS в этом конкретном финальном прогоне не был устойчиво
превышен, хотя c6 приблизился к нему. При этом p95 latency оставалась порядка
миллисекунд и существенно ниже ориентира 1 s.

### Repeated scaling sweep

Чтобы не делать вывод по одному удачному прогону, тот же release-like runtime
измерялся по три раза при c6/c8/c12. Каждый round — 1500 пар, то есть
3000 HTTP requests, с exact mask/demask checks и только `HTTP 200`.

| Concurrency | Median RPS | Min RPS | Max RPS | Worst MASK p95 | Worst DEMASK p95 |
|---:|---:|---:|---:|---:|---:|
| 6 | 933.4 | 914.7 | 984.7 | 11.589 ms | 10.599 ms |
| 8 | 848.5 | 822.0 | 854.9 | 23.040 ms | 17.695 ms |
| 12 | 682.3 | 492.5 | 718.0 | 52.989 ms | 35.599 ms |

На этой VM увеличение client concurrency выше c6 снижало throughput, поэтому
runtime не переводился на более высокую concurrency только ради единичной цифры.

Отдельный exploratory запуск с `--no-access-log` один раз дал c4 median
1045.3 RPS, но повторная проверка того же runtime-настройки дала median
901.5 RPS. Из-за отсутствия воспроизводимости этот tweak не был закоммичен
и результат >1000 RPS не используется как финальное доказательство.

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

На current runtime `49ebad0` отдельный HTTP smoke использовал synthetic payload
ровно из `100000 whitespace-separated units`.

Результат:

| Метрика | Значение |
|---|---:|
| Whitespace-separated units | 100000 |
| Characters | 700016 |
| UTF-8 bytes | 1300004 |
| Mask HTTP status | 200 |
| Mask latency | 227.753 ms |
| Demask HTTP status | 200 |
| Demask latency | 28.138 ms |
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
- полный regression suite на `49ebad0`: 189/189.

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
