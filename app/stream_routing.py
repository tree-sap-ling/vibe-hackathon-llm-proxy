import asyncio
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


@dataclass
class _StreamProviderAttempt:
    result: StreamingRoutingResult | None = None
    error: str | None = None
    terminal: bool = False


def _stream_routing_deadline(
    routing_timeout: float | None,
) -> float | None:
    if routing_timeout is None:
        return None

    loop = asyncio.get_running_loop()
    return loop.time() + max(0.0, routing_timeout)


def _stream_remaining_budget(
    deadline: float | None,
) -> float | None:
    if deadline is None:
        return None

    return deadline - asyncio.get_running_loop().time()


def _stream_budget_expired(
    remaining: float | None,
) -> bool:
    return remaining is not None and remaining <= 0


def _stream_error_or_default(
    error: str | None,
    default: str,
) -> str:
    if error is None:
        return default

    return error


async def _record_stream_failure(
    runtime,
    stats,
    error: str,
) -> None:
    await runtime.circuit_breaker.record_failure()

    if error == "unavailable":
        await stats.increment("upstream_errors")
        return

    await stats.increment("upstream_timeouts")


async def _open_stream_response(
    http_client,
    runtime,
    payload,
    stats,
    remaining: float | None,
) -> tuple[httpx.Response | None, str | None, bool]:
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
        if remaining is None:
            response = await http_client.send(
                upstream_request,
                stream=True,
            )
        else:
            async with asyncio.timeout(remaining):
                response = await http_client.send(
                    upstream_request,
                    stream=True,
                )

    except TimeoutError:
        await _record_stream_failure(
            runtime,
            stats,
            "timeout",
        )
        return None, "timeout", True

    except httpx.TimeoutException:
        await _record_stream_failure(
            runtime,
            stats,
            "timeout",
        )
        return None, "timeout", False

    except httpx.RequestError:
        await _record_stream_failure(
            runtime,
            stats,
            "unavailable",
        )
        return None, "unavailable", False

    return response, None, False


async def _read_first_stream_chunk(
    response: httpx.Response,
    stream_iterator: AsyncIterator[bytes],
    runtime,
    stats,
    remaining: float | None,
) -> tuple[bytes | None, str | None, bool]:
    try:
        if remaining is None:
            first_chunk = await anext(stream_iterator)
        else:
            async with asyncio.timeout(remaining):
                first_chunk = await anext(stream_iterator)

    except StopAsyncIteration:
        await response.aclose()
        await _record_stream_failure(
            runtime,
            stats,
            "unavailable",
        )
        return None, "unavailable", False

    except TimeoutError:
        await response.aclose()
        await _record_stream_failure(
            runtime,
            stats,
            "timeout",
        )
        return None, "timeout", True

    except httpx.TimeoutException:
        await response.aclose()
        await _record_stream_failure(
            runtime,
            stats,
            "timeout",
        )
        return None, "timeout", False

    except httpx.RequestError:
        await response.aclose()
        await _record_stream_failure(
            runtime,
            stats,
            "unavailable",
        )
        return None, "unavailable", False

    return first_chunk, None, False


async def _attempt_stream_provider(
    http_client,
    runtime,
    payload,
    stats,
    deadline: float | None,
) -> _StreamProviderAttempt:
    remaining = _stream_remaining_budget(deadline)

    if _stream_budget_expired(remaining):
        await stats.increment("upstream_timeouts")
        return _StreamProviderAttempt(
            result=StreamingRoutingResult(
                error="timeout"
            ),
            terminal=True,
        )

    response, error, terminal = await _open_stream_response(
        http_client,
        runtime,
        payload,
        stats,
        remaining,
    )

    if response is None:
        return _StreamProviderAttempt(
            error=_stream_error_or_default(
                error,
                "unavailable",
            ),
            terminal=terminal,
        )

    if response.status_code >= 500:
        await response.aclose()
        await runtime.circuit_breaker.record_failure()
        return _StreamProviderAttempt(
            error="upstream_5xx"
        )

    stream_iterator = response.aiter_raw()
    remaining = _stream_remaining_budget(deadline)

    if _stream_budget_expired(remaining):
        await response.aclose()
        await runtime.circuit_breaker.record_failure()
        await stats.increment("upstream_timeouts")
        return _StreamProviderAttempt(
            result=StreamingRoutingResult(
                error="timeout"
            ),
            terminal=True,
        )

    first_chunk, error, terminal = (
        await _read_first_stream_chunk(
            response,
            stream_iterator,
            runtime,
            stats,
            remaining,
        )
    )

    if first_chunk is None:
        return _StreamProviderAttempt(
            error=_stream_error_or_default(
                error,
                "unavailable",
            ),
            terminal=terminal,
        )

    return _StreamProviderAttempt(
        result=StreamingRoutingResult(
            response=response,
            provider_runtime=runtime,
            first_chunk=first_chunk,
            stream_iterator=stream_iterator,
        )
    )


async def route_stream_request(
    http_client,
    provider_runtimes,
    payload,
    stats,
    routing_timeout: float | None = None,
) -> StreamingRoutingResult:
    last_error = None
    deadline = _stream_routing_deadline(routing_timeout)

    for runtime in provider_runtimes:
        allowed = await runtime.circuit_breaker.allow_request()

        if not allowed:
            await stats.increment("circuit_open_rejections")

            if last_error is None:
                last_error = "circuit_open"

            continue

        attempt = await _attempt_stream_provider(
            http_client,
            runtime,
            payload,
            stats,
            deadline,
        )

        if attempt.result is not None:
            return attempt.result

        if attempt.terminal:
            return StreamingRoutingResult(error="timeout")

        last_error = _stream_error_or_default(
            attempt.error,
            "unavailable",
        )

    return StreamingRoutingResult(
        error=_stream_error_or_default(
            last_error,
            "no_provider",
        )
    )
