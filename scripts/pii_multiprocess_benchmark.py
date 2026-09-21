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


_PROCESSOR = None


def build_processor() -> PiiProcessor:
    policy = ConsumerPolicy(
        system_id="benchmark",
        enabled_types=frozenset(PiiType),
        demask_enabled=True,
    )
    return PiiProcessor(
        PolicyRegistry((policy,))
    )


def init_worker() -> None:
    global _PROCESSOR
    _PROCESSOR = build_processor()


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


def worker_request(
    text: str,
) -> tuple[float, int]:
    if _PROCESSOR is None:
        raise RuntimeError(
            "worker processor is not initialized"
        )

    started = time.perf_counter()

    prepared = _PROCESSOR.prepare_request(
        "benchmark",
        text,
    )

    elapsed_ms = (
        time.perf_counter() - started
    ) * 1000.0

    return elapsed_ms, prepared.entity_count


def run_case(
    processes: int,
    token_count: int,
    requests: int,
) -> None:
    text = build_synthetic_text(
        token_count
    )

    with concurrent.futures.ProcessPoolExecutor(
        max_workers=processes,
        initializer=init_worker,
    ) as executor:
        # Warm-up каждого процесса. Этот этап не входит
        # в измеряемое wall time.
        warmups = [
            executor.submit(
                worker_request,
                text,
            )
            for _ in range(processes)
        ]

        warmup_results = [
            future.result()
            for future in warmups
        ]

        if any(
            count < 1
            for _, count in warmup_results
        ):
            raise RuntimeError(
                "benchmark text produced no PII"
            )

        started = time.perf_counter()

        futures = [
            executor.submit(
                worker_request,
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
        f"processes={processes} "
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
            "Multi-process local benchmark "
            "for the PII prepare/mask pipeline."
        )
    )
    parser.add_argument(
        "--processes",
        nargs="+",
        type=int,
        default=[1, 2, 4],
    )
    args = parser.parse_args()

    print(
        "PII multi-process benchmark"
    )
    print(
        f"os.cpu_count={os.cpu_count()}"
    )
    print(
        "No network/upstream time is included."
    )

    cases = (
        (1_000, 240),
        (10_000, 80),
        (100_000, 12),
    )

    for token_count, requests in cases:
        print()
        print(
            f"=== payload {token_count:,} "
            "whitespace_tokens ==="
        )

        for processes in args.processes:
            if processes < 1:
                raise ValueError(
                    "processes must be positive"
                )

            run_case(
                processes,
                token_count,
                requests,
            )


if __name__ == "__main__":
    main()
