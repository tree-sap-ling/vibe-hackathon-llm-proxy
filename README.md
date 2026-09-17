# Vibe Hackathon — LLM Proxy

Preparation project for a high-load LLM proxy.

The goal is to build a small, reproducible proxy service that can:

- receive LLM chat requests;
- forward them to an upstream provider;
- stream responses;
- enforce timeout and overload limits;
- survive upstream failures with controlled fallback;
- expose health and operational metrics;
- scale horizontally;
- run without external API keys by using local mock providers.

## Important

The official hackathon task and autocheck contract are not known yet.

Everything in this repository before the official briefing is a reusable
technical foundation, not an assumption about the final API contract.

## Planned operating modes

### Self-contained mode

Runs entirely locally with deterministic mock LLM providers.

No VPN, external internet connection, or API key is required.

This mode will be used for:

- development;
- automated tests;
- load tests;
- failure simulation.

### Real upstream mode

Connects to a configurable OpenAI-compatible upstream endpoint.

Provider settings will be supplied through environment variables.
Real credentials must never be committed to Git.

## Initial technical direction

- Python 3.11+
- FastAPI
- async HTTP client
- streaming responses
- Docker
- deterministic mock upstreams
- automated tests
- load testing

Redis, a reverse proxy, multiple replicas, and a dashboard may be added
later when the basic request path is proven.

## Current status

Repository skeleton only.

Next milestone:

client -> proxy -> local mock provider -> response
