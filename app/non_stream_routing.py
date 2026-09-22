import asyncio
from dataclasses import dataclass

import httpx


@dataclass
class RoutingResult:
    response: httpx.Response | None = None
    error: str | None = None
    provider_name: str | None = None


def build_headers(api_key: str | None) -> dict[str, str]:
    if not api_key:
        return {}

    return {
        "Authorization": f"Bearer {api_key}",
    }


def _routing_deadline(
    routing_timeout: float | None,
) -> float | None:
    if routing_timeout is None:
        return None

    loop = asyncio.get_running_loop()
    return loop.time() + max(0.0, routing_timeout)


def _remaining_budget(
    deadline: float | None,
) -> float | None:
    if deadline is None:
        return None

    return deadline - asyncio.get_running_loop().time()


def _budget_expired(
    remaining: float | None,
) -> bool:
    return remaining is not None and remaining <= 0


async def _post_non_stream(
    http_client,
    runtime,
    payload,
    remaining: float | None,
) -> tuple[httpx.Response | None, str | None, bool]:
    upstream_url = (
        f"{runtime.config.base_url}/v1/chat/completions"
    )

    try:
        if remaining is None:
            response = await http_client.post(
                upstream_url,
                json=payload,
                headers=build_headers(runtime.config.api_key),
            )
        else:
            async with asyncio.timeout(remaining):
                response = await http_client.post(
                    upstream_url,
                    json=payload,
                    headers=build_headers(
                        runtime.config.api_key
                    ),
                )

    except TimeoutError:
        return None, "timeout", True

    except httpx.TimeoutException:
        return None, "timeout", False

    except httpx.RequestError:
        return None, "unavailable", False

    return response, None, False


async def _record_non_stream_failure(
    runtime,
    stats,
    error: str,
) -> None:
    await runtime.circuit_breaker.record_failure()

    if error == "unavailable":
        await stats.increment("upstream_errors")
        return

    await stats.increment("upstream_timeouts")


def _non_stream_error_or_default(
    error: str | None,
    default: str,
) -> str:
    if error is None:
        return default

    return error


async def route_non_stream_request(
    http_client,
    provider_runtimes,
    payload,
    stats,
    routing_timeout: float | None = None,
) -> RoutingResult:
    last_error = None
    deadline = _routing_deadline(routing_timeout)

    for runtime in provider_runtimes:
        allowed = await runtime.circuit_breaker.allow_request()

        if not allowed:
            await stats.increment("circuit_open_rejections")

            if last_error is None:
                last_error = "circuit_open"

            continue

        remaining = _remaining_budget(deadline)

        if _budget_expired(remaining):
            await stats.increment("upstream_timeouts")
            return RoutingResult(error="timeout")

        response, error, terminal = await _post_non_stream(
            http_client,
            runtime,
            payload,
            remaining,
        )

        if response is None:
            failure_error = _non_stream_error_or_default(
                error,
                "unavailable",
            )

            await _record_non_stream_failure(
                runtime,
                stats,
                failure_error,
            )

            if terminal:
                return RoutingResult(error="timeout")

            last_error = failure_error
            continue

        if response.status_code >= 500:
            await runtime.circuit_breaker.record_failure()
            last_error = "upstream_5xx"
            continue

        await runtime.circuit_breaker.record_success()

        return RoutingResult(
            response=response,
            provider_name=runtime.config.name,
        )

    return RoutingResult(
        error=_non_stream_error_or_default(
            last_error,
            "no_provider",
        )
    )
