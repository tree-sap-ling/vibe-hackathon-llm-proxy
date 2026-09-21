import argparse
import concurrent.futures
import math
import os
import statistics
import time

from app.pii import (
    ConsumerPolicy,
    PiiProcessor,
    PiiType,
    PolicyRegistry,
)


def build_processor() -> PiiProcessor:
    policy = ConsumerPolicy(
        system_id="benchmark",
        enabled_types=frozenset(PiiType),
        demask_enabled=True,
    )
    return PiiProcessor(
        PolicyRegistry((policy,))
    )


def build_synthetic_text(
    token_count: int,
) -> str:
    if token_count < 1:
        raise ValueError(
            "token_count must be positive"
        )

    tokens = ["данные"] * token_count

    samples = (
        "bench.person@example.com",
        "+79991234567",
        "4111111111111111",
        "Дата рождения: 15.05.1990",
        "CVV 123",
        "PIN 4321",
        "ФИО: Иванов Иван Иванович",
    )

    stride = max(
        token_count // 20,
        1,
    )

    sample_index = 0

    for index in range(
        stride - 1,
        token_count,
        stride,
    ):
        tokens[index] = samples[
            sample_index % len(samples)
        ]
        sample_index += 1

    return " ".join(tokens)


def percentile(
    values: list[float],
    fraction: float,
) -> float:
    ordered = sorted(values)
    rank = max(
        1,
        math.ceil(
            fraction * len(ordered)
        ),
    )
    return ordered[rank - 1]


def one_request(
    processor: PiiProcessor,
    text: str,
) -> tuple[float, int]:
    started = time.perf_counter()

    prepared = processor.prepare_request(
        "benchmark",
        text,
    )

    elapsed_ms = (
        time.perf_counter() - started
    ) * 1000.0

    return elapsed_ms, prepared.entity_count


def run_case(
    processor: PiiProcessor,
    token_count: int,
    workers: int,
    requests: int,
) -> None:
    text = build_synthetic_text(
        token_count
    )

    # Warm-up.
    warmup = processor.prepare_request(
        "benchmark",
        text,
    )

    if warmup.entity_count < 1:
        raise RuntimeError(
            "benchmark text produced no PII"
        )

    started = time.perf_counter()

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=workers
    ) as executor:
        futures = [
            executor.submit(
                one_request,
                processor,
                text,
            )
            for _ in range(requests)
        ]

        results = [
            future.result()
            for future in futures
        ]

    wall_seconds = (
        time.perf_counter() - started
    )

    latencies = [
        latency
        for latency, _ in results
    ]

    counts = [
        count
        for _, count in results
    ]

    rps = (
        requests / wall_seconds
        if wall_seconds > 0
        else float("inf")
    )

    print(
        f"size={token_count:,} "
        f"workers={workers} "
        f"requests={requests} "
        f"wall={wall_seconds:.3f}s "
        f"rps={rps:.2f}"
    )
    print(
        f"  entities={min(counts)}"
        f"..{max(counts)} "
        f"p50={statistics.median(latencies):.3f} ms "
        f"p95={percentile(latencies, 0.95):.3f} ms "
        f"p99={percentile(latencies, 0.99):.3f} ms "
        f"max={max(latencies):.3f} ms"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Threaded local concurrency benchmark "
            "for the PII prepare/mask pipeline."
        )
    )
    parser.add_argument(
        "--workers",
        nargs="+",
        type=int,
        default=[1, 2, 4, 8],
    )
    args = parser.parse_args()

    processor = build_processor()

    print(
        "PII concurrency benchmark: "
        "single Python process"
    )
    print(
        f"os.cpu_count={os.cpu_count()}"
    )
    print(
        "No network/upstream time is included."
    )

    cases = (
        (1_000, 200),
        (10_000, 60),
        (100_000, 8),
    )

    for token_count, requests in cases:
        print()
        print(
            f"=== payload {token_count:,} "
            "whitespace_tokens ==="
        )

        for workers in args.workers:
            if workers < 1:
                raise ValueError(
                    "workers must be positive"
                )

            run_case(
                processor,
                token_count,
                workers,
                requests,
            )


if __name__ == "__main__":
    main()
