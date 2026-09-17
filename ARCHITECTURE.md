# Architecture

## Purpose

Build a reusable foundation for a high-load LLM proxy while keeping the
system simple enough to adapt quickly after the official hackathon briefing.

## Core request path

Initial version:

Client
  |
  v
LLM Proxy
  |
  v
Mock or OpenAI-compatible upstream

Later versions may evolve toward:

Clients
  |
  v
Load balancer
  |
  +--> Proxy replica
  +--> Proxy replica
  +--> Proxy replica
           |
           v
      Routing / resilience
           |
           +--> Provider A
           +--> Provider B
           +--> Mock provider

Shared state such as distributed rate limits or health information may use
Redis only if the final requirements justify it.

## Design principles

1. Keep the hot path asynchronous.
2. Stream output instead of buffering complete LLM responses.
3. Reuse upstream HTTP connections.
4. Apply explicit timeout budgets.
5. Bound concurrency instead of allowing unlimited queued work.
6. Reject overload quickly rather than letting latency grow without bound.
7. Keep provider-specific code behind adapters.
8. Make failures observable.
9. Keep the proxy stateless where practical so replicas can scale horizontally.
10. Keep local development independent from external LLM services.

## Failure handling

Before the first streamed token is sent, a request may potentially be retried
or routed to another healthy provider.

After output has already been streamed to the client, silently switching to
another provider can duplicate or corrupt the response. In that case the
stream should fail cleanly and the failure should be recorded.

## Planned endpoints

These are preparation-time conventions only and may change after the official
briefing.

- POST /v1/chat/completions
- GET /healthz
- GET /readyz
- GET /stats

## Development phases

Phase 1:
local mock provider + minimal async proxy

Phase 2:
streaming + timeout handling

Phase 3:
bounded concurrency + overload protection

Phase 4:
fallback + provider health + circuit breaker

Phase 5:
load tests + metrics

Phase 6:
horizontal scaling and shared state if required

## Non-goals for the initial version

Do not add complexity before it is justified:

- Kubernetes
- Kafka
- PostgreSQL
- vector databases
- agent frameworks
- semantic caching
- an LLM-based router in the request hot path

## Unknowns

The following must be confirmed from the official task:

- exact API contract;
- autocheck startup procedure;
- required port and entrypoint;
- Docker / Docker Compose availability;
- internet availability;
- supplied LLM endpoint and credentials;
- SLA definition;
- expected concurrency and request rate;
- streaming requirements;
- failure scenarios used by autocheck;
- CPU and memory limits;
- caching rules;
- persistence requirements.
