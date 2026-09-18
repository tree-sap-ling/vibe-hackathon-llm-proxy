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


async def route_non_stream_request(
    http_client,
    provider_runtimes,
    payload,
    stats,
    routing_timeout: float | None = None,
) -> RoutingResult:
    last_error = None

    deadline = None

    if routing_timeout is not None:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + max(0.0, routing_timeout)

    for runtime in provider_runtimes:
        allowed = await runtime.circuit_breaker.allow_request()

        if not allowed:
            await stats.increment("circuit_open_rejections")

            if last_error is None:
                last_error = "circuit_open"

            continue

        remaining = None

        if deadline is not None:
            remaining = deadline - asyncio.get_running_loop().time()

            if remaining <= 0:
                await stats.increment("upstream_timeouts")
                return RoutingResult(error="timeout")

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
            await runtime.circuit_breaker.record_failure()
            await stats.increment("upstream_timeouts")

            return RoutingResult(error="timeout")

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
            await runtime.circuit_breaker.record_failure()
            last_error = "upstream_5xx"
            continue

        await runtime.circuit_breaker.record_success()

        return RoutingResult(
            response=response,
            provider_name=runtime.config.name,
        )

    return RoutingResult(error=last_error or "no_provider")
