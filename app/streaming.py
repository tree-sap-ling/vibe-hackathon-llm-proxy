import httpx


async def relay_stream(
    upstream_response: httpx.Response,
    stats,
    concurrency_gate,
    circuit_breaker,
):
    completed = False
    failure_recorded = False

    try:
        async for chunk in upstream_response.aiter_raw():
            yield chunk

        completed = True

    except httpx.TimeoutException:
        await stats.increment("upstream_timeouts")
        await circuit_breaker.record_failure()
        failure_recorded = True

    except httpx.RequestError:
        await stats.increment("upstream_errors")
        await circuit_breaker.record_failure()
        failure_recorded = True

    finally:
        await upstream_response.aclose()

        if completed:
            await stats.increment("completed_requests")

            if upstream_response.status_code >= 500:
                await circuit_breaker.record_failure()
            else:
                await circuit_breaker.record_success()

        elif not failure_recorded:
            await circuit_breaker.record_failure()

        await concurrency_gate.release()
