import argparse
import asyncio
import time

import httpx


async def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8000/v1/chat/completions",
    )
    parser.add_argument("--first-delay-ms", type=int, default=500)
    parser.add_argument("--chunk-delay-ms", type=int, default=300)
    parser.add_argument(
        "--message",
        default="hello streaming world",
    )

    args = parser.parse_args()

    payload = {
        "model": "mock-model",
        "stream": True,
        "mock_delay_ms": args.first_delay_ms,
        "mock_chunk_delay_ms": args.chunk_delay_ms,
        "messages": [
            {
                "role": "user",
                "content": args.message,
            }
        ],
    }

    started = time.perf_counter()
    first_data_at = None
    data_events = 0

    async with httpx.AsyncClient(timeout=30.0) as client:
        async with client.stream(
            "POST",
            args.url,
            json=payload,
        ) as response:
            print(f"HTTP status: {response.status_code}")

            response.raise_for_status()

            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue

                value = line[len("data: "):]

                if value == "[DONE]":
                    break

                data_events += 1

                if first_data_at is None:
                    first_data_at = time.perf_counter()

    finished = time.perf_counter()

    total_ms = (finished - started) * 1000

    if first_data_at is None:
        print("TTFT: no data received")
    else:
        ttft_ms = (first_data_at - started) * 1000
        print(f"TTFT:       {ttft_ms:.1f} ms")

    print(f"Total time: {total_ms:.1f} ms")
    print(f"Data events: {data_events}")


if __name__ == "__main__":
    asyncio.run(main())
