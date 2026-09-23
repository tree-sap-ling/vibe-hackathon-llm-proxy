# Архитектура PII Protection Service

## Назначение

Основной конкурсный path — `POST /process`.

Сервис принимает строку и `payload_id`, обнаруживает персональные данные,
возвращает маску, а при повторном запросе с тем же `payload_id` и ранее
выданной маской восстанавливает исходную строку.

Ключевые свойства текущей реализации:

- обработка `/process` полностью локальная, без вызова внешней LLM;
- детектирование ПД построено как расширяемый registry детекторов;
- маскирование обратимое и изолировано между запросами;
- корреляция mask → demask идемпотентна по `payload_id`;
- исходные значения ПД не пишутся в audit logs и technical metrics;
- overload для `/process` возвращает `HTTP 429` + `Retry-After: 1`;
- correlation state хранится в памяти процесса, поэтому конкурсный runtime
  запускается одним HTTP worker.

## Конкурсный request path

```text
Client
  |
  v
POST /process
  |
  v
PROCESS_MAX_IN_FLIGHT gate
  |
  +--> limit exceeded -> HTTP 429 + Retry-After: 1
  |
  v
CorrelationStore lookup by payload_id
  |
  +--> new payload_id
  |      |
  |      v
  |   PiiProcessor.prepare_request()
  |      |
  |      +--> detector registry
  |      +--> overlap resolution
  |      +--> internal token-mask + reversible MaskingVault
  |      +--> exact PiiEntity spans
  |      |
  |      v
  |   render_public_mask(original, prepared.entities)
  |      |
  |      v
  |   save correlation record
  |      +--> public masked_payload
  |      +--> PreparedRequest with internal token-mask/vault
  |      |
  |      v
  |   return public shape-mask
  |
  +--> known payload_id + original retry
  |      |
  |      v
  |   return exact same mask
  |
  +--> known payload_id + issued mask
  |      |
  |      v
  |   demask through stored vault
  |      |
  |      v
  |   return exact original
  |
  +--> conflicting payload
         |
         v
      HTTP 409
```

## PII pipeline

`PiiProcessor` получает policy для system/consumer и вызывает registry
детекторов только для разрешённых типов ПД.

Результат `PiiProcessor.prepare_request()` содержит:

- внутреннюю technical token-mask;
- набор обнаруженных типов ПД;
- immutable tuple точных `PiiEntity` spans;
- количество сущностей;
- время локальной PII-обработки;
- request-local vault для обратного восстановления.

`PiiEntity` хранит тип, `start`, `end` и confidence, но не копирует
исходное PII-значение в отдельное поле.

Сами исходные значения ПД не входят в safe observability structures.

## Детекторы

Registry поддерживает отдельные типы ПД из задания, включая:

- ФИО;
- дату и место рождения;
- паспорт РФ, орган выдачи, код подразделения и дату выдачи;
- гражданство;
- водительское удостоверение;
- адрес и его компоненты;
- email и телефон;
- ИНН;
- банковскую карту;
- CVV/CVC;
- PIN;
- имя держателя карты.

Для структурированных значений используются контекстные правила и,
где применимо, checksum validation. Overlap resolution выбирает одну
согласованную систему spans перед маскированием.

## Dual masking: internal tokens и public shape-mask

В runtime используются два разных представления маски.

### Internal technical mask

`PiiProcessor.prepare_request()` по-прежнему создаёт request-local
`MaskingVault` и внутренние tokens вида:

```text
<PII:email:1:request_namespace>
```

Namespace случайный и изолирует значения разных запросов. Эти tokens
нужны только внутри процесса: vault умеет по ним точно восстановить
исходный текст.

### Public mask для `/process`

После единственного detector pass `render_public_mask()` использует
`prepared.entities` и строит внешний ответ checker-у.

Публичная маска полностью скрывает буквенно-цифровые символы внутри
найденного PII span. Разделители сохраняются, а для некоторых
структурированных типов renderer также сохраняет известные служебные
маркеры.

Например:

```text
Клиент Иванов Иван Иванович, паспорт 4509 123456
→
Клиент ****** **** ********, паспорт **** ******
```

Для ФИО все буквенные символы внутри найденного span заменяются на `*`;
для российского паспорта все цифры внутри span также заменяются на `*`.
Exact demask не зависит от внешнего вида public mask: исходное значение
восстанавливается через сохранённые `PreparedRequest.masked_text` и
request-local vault/correlation record.

Public response `/process` не содержит внутренних `<PII:...>` tokens.

### Demask

`CorrelationRecord.masked_payload` хранит именно public mask, чтобы
второй запрос checker-а распознавался по тому же `payload_id`.
Для восстановления original endpoint не пытается разобрать `*`-маску:
он использует сохранённые `PreparedRequest.masked_text` и request-local
vault, то есть exact demask остаётся обратимым.

Неизвестный или чужой internal token не раскрывает данные.

## Correlation store и идемпотентность

`InMemoryCorrelationStore` хранит состояние пары запросов для `/process`.

Поведение:

- первый новый `payload_id` создаёт record с public `masked_payload`
  и внутренним `PreparedRequest`/vault;
- retry исходного payload возвращает ту же public mask;
- issued public mask с тем же `payload_id` возвращает exact original;
- retry demask снова возвращает original;
- другой payload для существующего `payload_id` считается конфликтом.

TTL текущей реализации:

- pending record: 15 минут;
- completed record: 120 секунд;
- периодический полный cleanup: 5 секунд.

Короткий TTL completed-record сохраняет окно для retry и ограничивает рост памяти.

## Overload protection

Для `/process` используется отдельный `ConcurrencyGate`.

Переменная:

```text
PROCESS_MAX_IN_FLIGHT=50
```

Если slot недоступен, endpoint отвечает:

```text
HTTP 429 Too Many Requests
Retry-After: 1
```

После успешного acquire request task делает один cooperative event-loop yield,
чтобы одновременно готовые requests могли увидеть занятые admission slots.
Освобождение slot защищено `try/finally`.

Этот gate ограничивает задачи, уже дошедшие до application handler.
Он не является заменой TCP/server-level admission control.

## Safe observability

PII audit event содержит только:

- случайный internal `request_id`;
- `system_id`;
- обнаруженные типы ПД;
- количество сущностей;
- processing latency;
- флаг demask policy.

Audit log не должен содержать:

- исходный payload;
- значения ПД;
- выданную mask;
- `payload_id`.

`GET /stats` публикует только агрегированные PII metrics:
число обработанных запросов, requests with PII, число сущностей,
latency percentiles и counters по типам ПД.

## Single-process deployment

Correlation store находится в памяти Python-процесса.

Поэтому текущий конкурсный deployment должен использовать один Uvicorn worker.
Несколько независимых workers не разделяли бы correlation state и могли бы
разнести mask и demask одного `payload_id` по разным процессам.

Горизонтальное масштабирование возможно только после добавления shared
correlation storage и стратегии маршрутизации/консистентности. Сейчас это
намеренно не входит в hot path.

## Docker

Docker image основан на `python:3.12-slim`.

Приложение запускается непривилегированным пользователем:

```text
USER app
```

Container command:

```text
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

`--workers` намеренно не задаётся: Uvicorn запускает один worker.

## Health и runtime endpoints

### `GET /healthz`

Liveness самого приложения.

### `GET /readyz`

Readiness старого LLM-proxy subsystem относительно настроенных upstream providers.
Для конкурсного `/process` внешний provider не требуется.

### `GET /stats`

Process-local technical metrics без исходных PII values.

## LLM proxy subsystem

В проекте сохранён подготовленный ранее `/v1/chat/completions` foundation.

Он включает:

- shared `httpx.AsyncClient`;
- primary/fallback provider routing;
- circuit breaker на каждого provider;
- общий routing time budget;
- bounded concurrency через `MAX_IN_FLIGHT`;
- SSE streaming;
- fallback только до первого видимого client chunk.

Для LLM proxy overload используется `HTTP 503`.
Этот subsystem не участвует в официальной логике mask/demask `/process`.

## Что остаётся неизвестным до официального прогона

Опубликованный контракт и правила нагрузки известны, но организаторы не раскрывают:

- скрытый эталонный датасет;
- точные reference spans для всех строк;
- точные reference replacement strings за пределами опубликованных примеров;
- внутреннюю реализацию scorer-а сверх описанной span-based normalized
  Levenshtein metric.

Поэтому нельзя утверждать, что локальная точность равна официальной
или что достигнут официальный target 95%, пока решение не измерено
проверяющей системой организаторов.
