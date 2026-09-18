from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx

from app.non_stream_routing import build_headers


@dataclass
class StreamingRoutingResult:
    response: httpx.Response | None = None
    provider_runtime: object | None = None
    first_chunk: bytes | None = None
    stream_iterator: AsyncIterator[bytes] | None = None
    error: str | None = None


async def route_stream_request(
    http_client,
    provider_runtimes,
    payload,
    stats,
) -> StreamingRoutingResult:
    last_error = None

    for runtime in provider_runtimes:
        allowed = await runtime.circuit_breaker.allow_request()

        if not allowed:
            await stats.increment("circuit_open_rejections")

            if last_error is None:
                last_error = "circuit_open"

            continue

        upstream_url = (
            f"{runtime.config.base_url}/v1/chat/completions"
        )

        upstream_request = http_client.build_request(
            "POST",
            upstream_url,
            json=payload,
            headers=build_headers(runtime.config.api_key),
        )

        try:
            response = await http_client.send(
                upstream_request,
                stream=True,
            )

        except httpx.TimeoutException:
            await runtime.circuit_breaker.record_failure()
            await stats.increment("upstream_timeouts")
            last_error = "timeout"
            continue

        except httpx.RequestError:
            await runtime.circuit_breaker.record_failure()
            await stats.increment("upstream_errors")
            last_error = "unavailable"
            continue

        if response.status_code >= 500:
            await response.aclose()
            await runtime.circuit_breaker.record_failure()
            last_error = "upstream_5xx"
            continue

        stream_iterator = response.aiter_raw()

        try:
            first_chunk = await anext(stream_iterator)

        except StopAsyncIteration:
            await response.aclose()
            await runtime.circuit_breaker.record_failure()
            await stats.increment("upstream_errors")
            last_error = "unavailable"
            continue

        except httpx.TimeoutException:
            await response.aclose()
            await runtime.circuit_breaker.record_failure()
            await stats.increment("upstream_timeouts")
            last_error = "timeout"
            continue

        except httpx.RequestError:
            await response.aclose()
            await runtime.circuit_breaker.record_failure()
            await stats.increment("upstream_errors")
            last_error = "unavailable"
            continue

        return StreamingRoutingResult(
            response=response,
            provider_runtime=runtime,
            first_chunk=first_chunk,
            stream_iterator=stream_iterator,
        )

    return StreamingRoutingResult(
        error=last_error or "no_provider"
    )
