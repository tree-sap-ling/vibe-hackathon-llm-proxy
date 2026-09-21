import asyncio
import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.non_stream_routing import route_non_stream_request
from app.provider_runtime import build_provider_runtimes
from app.providers import get_provider_configs
from app.pii import PiiMetrics
from app.stats import ProxyStats
from app.stream_routing import route_stream_request
from app.streaming import relay_stream


class ConcurrencyGate:
    def __init__(self, limit: int):
        self.limit = limit
        self.in_flight = 0
        self.lock = asyncio.Lock()

    async def try_acquire(self) -> bool:
        async with self.lock:
            if self.in_flight >= self.limit:
                return False

            self.in_flight += 1
            return True

    async def release(self) -> None:
        async with self.lock:
            self.in_flight -= 1

    async def snapshot(self):
        async with self.lock:
            return {
                "in_flight": self.in_flight,
                "max_in_flight": self.limit,
            }


def get_upstream_base_url():
    return os.getenv(
        "UPSTREAM_BASE_URL",
        "http://127.0.0.1:9000",
    ).rstrip("/")


def get_max_in_flight():
    raw_value = os.getenv("MAX_IN_FLIGHT", "2")

    try:
        value = int(raw_value)
    except ValueError:
        value = 2

    return max(1, value)


def get_routing_timeout():
    raw_value = os.getenv(
        "ROUTING_TIMEOUT_SECONDS",
        "5",
    )

    try:
        value = float(raw_value)
    except ValueError:
        value = 5.0

    return max(0.001, value)


def get_circuit_failure_threshold():
    raw_value = os.getenv(
        "CIRCUIT_FAILURE_THRESHOLD",
        "3",
    )

    try:
        value = int(raw_value)
    except ValueError:
        value = 3

    return max(1, value)


def get_circuit_recovery_timeout():
    raw_value = os.getenv(
        "CIRCUIT_RECOVERY_TIMEOUT_SECONDS",
        "5",
    )

    try:
        value = float(raw_value)
    except ValueError:
        value = 5.0

    return max(0.0, value)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(5.0)
    )

    app.state.concurrency_gate = ConcurrencyGate(
        limit=get_max_in_flight()
    )
    app.state.stats = ProxyStats()
    app.state.pii_metrics = PiiMetrics()
    app.state.routing_timeout = get_routing_timeout()

    app.state.provider_runtimes = build_provider_runtimes(
        providers=get_provider_configs(),
        failure_threshold=get_circuit_failure_threshold(),
        recovery_timeout=get_circuit_recovery_timeout(),
    )

    # Temporary compatibility alias.
    # Existing request code still uses the primary provider breaker.
    app.state.circuit_breaker = (
        app.state.provider_runtimes[0].circuit_breaker
    )

    yield

    await app.state.http_client.aclose()


app = FastAPI(
    title="LLM Proxy",
    lifespan=lifespan,
)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/stats")
async def stats(request: Request):
    counters = await request.app.state.stats.snapshot()
    concurrency = await request.app.state.concurrency_gate.snapshot()
    pii_metrics = await request.app.state.pii_metrics.snapshot()
    circuit = await request.app.state.circuit_breaker.snapshot()

    providers = {}

    for runtime in request.app.state.provider_runtimes:
        providers[runtime.config.name] = {
            "circuit": (
                await runtime.circuit_breaker.snapshot()
            )
        }

    return {
        **concurrency,
        **counters,
        "circuit": circuit,
        "providers": providers,
        "pii": pii_metrics,
    }


@app.get("/readyz")
async def readyz(request: Request):
    for runtime in request.app.state.provider_runtimes:
        upstream_url = (
            f"{runtime.config.base_url}/healthz"
        )

        try:
            upstream_response = (
                await request.app.state.http_client.get(
                    upstream_url,
                    timeout=1.0,
                )
            )
            upstream_response.raise_for_status()
        except httpx.HTTPError:
            continue

        return {"status": "ready"}

    return JSONResponse(
        status_code=503,
        content={"status": "not_ready"},
    )


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    await request.app.state.stats.increment("total_requests")

    acquired = await request.app.state.concurrency_gate.try_acquire()

    if not acquired:
        await request.app.state.stats.increment(
            "overload_rejections"
        )
        raise HTTPException(
            status_code=503,
            detail="Proxy overloaded",
        )

    release_gate = True

    try:
        payload = await request.json()

        upstream_url = (
            f"{get_upstream_base_url()}/v1/chat/completions"
        )

        if payload.get("stream") is True:
            routing_result = await route_stream_request(
                request.app.state.http_client,
                request.app.state.provider_runtimes,
                payload,
                request.app.state.stats,
                routing_timeout=request.app.state.routing_timeout,
            )

            if routing_result.response is None:
                if routing_result.error == "timeout":
                    raise HTTPException(
                        status_code=504,
                        detail="Upstream provider timed out",
                    )

                if routing_result.error == "circuit_open":
                    raise HTTPException(
                        status_code=503,
                        detail="Upstream circuit is open",
                    )

                if routing_result.error == "upstream_5xx":
                    raise HTTPException(
                        status_code=502,
                        detail="Upstream provider failed",
                    )

                raise HTTPException(
                    status_code=502,
                    detail="Upstream provider is unavailable",
                )

            upstream_response = routing_result.response
            provider_runtime = routing_result.provider_runtime

            content_type = upstream_response.headers.get(
                "content-type"
            )

            response_headers = {}

            if content_type:
                response_headers["content-type"] = content_type

            release_gate = False

            return StreamingResponse(
                relay_stream(
                    upstream_response,
                    request.app.state.stats,
                    request.app.state.concurrency_gate,
                    provider_runtime.circuit_breaker,
                    first_chunk=routing_result.first_chunk,
                    stream_iterator=routing_result.stream_iterator,
                ),
                status_code=upstream_response.status_code,
                headers=response_headers,
                media_type=(
                    None
                    if content_type
                    else "text/event-stream"
                ),
            )

        routing_result = await route_non_stream_request(
            request.app.state.http_client,
            request.app.state.provider_runtimes,
            payload,
            request.app.state.stats,
            routing_timeout=request.app.state.routing_timeout,
        )

        if routing_result.response is not None:
            await request.app.state.stats.increment(
                "completed_requests"
            )

            return JSONResponse(
                status_code=routing_result.response.status_code,
                content=routing_result.response.json(),
            )

        if routing_result.error == "timeout":
            raise HTTPException(
                status_code=504,
                detail="Upstream provider timed out",
            )

        if routing_result.error == "circuit_open":
            raise HTTPException(
                status_code=503,
                detail="Upstream circuit is open",
            )

        if routing_result.error == "upstream_5xx":
            raise HTTPException(
                status_code=502,
                detail="Upstream provider failed",
            )

        raise HTTPException(
            status_code=502,
            detail="Upstream provider is unavailable",
        )
    finally:
        if release_gate:
            await request.app.state.concurrency_gate.release()
