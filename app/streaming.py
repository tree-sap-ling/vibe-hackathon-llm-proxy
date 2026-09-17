import httpx


async def relay_stream(
    upstream_response: httpx.Response,
    stats,
    concurrency_gate,
):
    completed = False

    try:
        async for chunk in upstream_response.aiter_raw():
            yield chunk

        completed = True
    except httpx.TimeoutException:
        await stats.increment("upstream_timeouts")
    except httpx.RequestError:
        await stats.increment("upstream_errors")
    finally:
        await upstream_response.aclose()

        if completed:
            await stats.increment("completed_requests")

        await concurrency_gate.release()
