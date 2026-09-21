import argparse
import math
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


def run_case(
    processor: PiiProcessor,
    token_count: int,
    repetitions: int,
) -> None:
    text = build_synthetic_text(
        token_count
    )

    # Warm-up: исключаем первый запуск из измерений.
    warmup = processor.prepare_request(
        "benchmark",
        text,
    )

    if warmup.entity_count < 1:
        raise RuntimeError(
            "benchmark text produced no PII"
        )

    latencies_ms = []
    entity_counts = []

    for _ in range(repetitions):
        started = time.perf_counter()

        prepared = processor.prepare_request(
            "benchmark",
            text,
        )

        elapsed_ms = (
            time.perf_counter() - started
        ) * 1000.0

        latencies_ms.append(
            elapsed_ms
        )
        entity_counts.append(
            prepared.entity_count
        )

    p50 = statistics.median(
        latencies_ms
    )
    p95 = percentile(
        latencies_ms,
        0.95,
    )
    p99 = percentile(
        latencies_ms,
        0.99,
    )

    chars = len(text)
    utf8_bytes = len(
        text.encode("utf-8")
    )

    print(
        f"size={token_count:,} whitespace_tokens "
        f"chars={chars:,} "
        f"bytes={utf8_bytes:,} "
        f"runs={repetitions}"
    )
    print(
        f"  entities={min(entity_counts)}"
        f"..{max(entity_counts)} "
        f"p50={p50:.3f} ms "
        f"p95={p95:.3f} ms "
        f"p99={p99:.3f} ms "
        f"max={max(latencies_ms):.3f} ms"
    )

    tokens_per_second = (
        token_count
        / (p50 / 1000.0)
        if p50 > 0
        else float("inf")
    )

    print(
        f"  p50 throughput≈"
        f"{tokens_per_second:,.0f} "
        f"whitespace_tokens/s"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Local benchmark for the PII "
            "prepare/mask pipeline."
        )
    )
    parser.add_argument(
        "--sizes",
        nargs="+",
        type=int,
        default=[
            1_000,
            10_000,
            100_000,
        ],
    )
    args = parser.parse_args()

    processor = build_processor()

    print(
        "PII benchmark: local CPU pipeline only"
    )
    print(
        "No upstream LLM/network time is included."
    )
    print(
        "Input values are synthetic and are not logged."
    )

    for size in args.sizes:
        if size <= 1_000:
            repetitions = 20
        elif size <= 10_000:
            repetitions = 10
        else:
            repetitions = 3

        run_case(
            processor,
            size,
            repetitions,
        )


if __name__ == "__main__":
    main()
