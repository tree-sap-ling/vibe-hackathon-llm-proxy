import argparse
import asyncio
import math
import time
from collections import Counter

import httpx


def percentile(values, fraction):
    if not values:
        return 0.0

    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * fraction) - 1)
    return ordered[index]


async def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8000/v1/chat/completions",
    )
    parser.add_argument("--requests", type=int, default=20)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--delay-ms", type=int, default=1000)

    args = parser.parse_args()

    semaphore = asyncio.Semaphore(args.concurrency)
    results = []

    async with httpx.AsyncClient(timeout=10.0) as client:

        async def send_request(request_id):
            async with semaphore:
                started = time.perf_counter()

                try:
                    response = await client.post(
                        args.url,
                        json={
                            "model": "mock-model",
                            "mock_delay_ms": args.delay_ms,
                            "messages": [
                                {
                                    "role": "user",
                                    "content": f"load-{request_id}",
                                }
                            ],
                        },
                    )

                    status = str(response.status_code)

                except httpx.HTTPError:
                    status = "client_error"

                elapsed_ms = (
                    time.perf_counter() - started
                ) * 1000

                results.append(
                    (status, elapsed_ms)
                )

        started = time.perf_counter()

        await asyncio.gather(
            *[
                send_request(request_id)
                for request_id in range(args.requests)
            ]
        )

        total_seconds = time.perf_counter() - started

    statuses = Counter(
        status for status, _ in results
    )

    latencies = [
        latency for _, latency in results
    ]

    successful_latencies = [
        latency
        for status, latency in results
        if status == "200"
    ]

    successful_requests = statuses.get("200", 0)
    overload_rejections = statuses.get("503", 0)

    print()
    print("Load test results")
    print("-----------------")
    print(f"Requests:    {args.requests}")
    print(f"Concurrency: {args.concurrency}")
    print(f"Delay:       {args.delay_ms} ms")
    print(f"Duration:    {total_seconds:.3f} s")

    if total_seconds > 0:
        print(
            f"Throughput:  "
            f"{args.requests / total_seconds:.2f} req/s"
        )
        print(
            f"Successful:  "
            f"{successful_requests / total_seconds:.2f} req/s"
        )

    if args.requests > 0:
        print(
            f"Success rate: "
            f"{successful_requests / args.requests * 100:.1f}%"
        )
        print(
            f"Reject rate:  "
            f"{overload_rejections / args.requests * 100:.1f}%"
        )

    print()
    print("Statuses:")

    for status, count in sorted(statuses.items()):
        print(f"  {status}: {count}")

    print()
    print("Latency - all responses:")
    print(f"  p50: {percentile(latencies, 0.50):.1f} ms")
    print(f"  p95: {percentile(latencies, 0.95):.1f} ms")
    print(f"  p99: {percentile(latencies, 0.99):.1f} ms")

    print()
    print("Latency - successful 200 responses:")
    print(
        f"  p50: "
        f"{percentile(successful_latencies, 0.50):.1f} ms"
    )
    print(
        f"  p95: "
        f"{percentile(successful_latencies, 0.95):.1f} ms"
    )
    print(
        f"  p99: "
        f"{percentile(successful_latencies, 0.99):.1f} ms"
    )


if __name__ == "__main__":
    asyncio.run(main())
