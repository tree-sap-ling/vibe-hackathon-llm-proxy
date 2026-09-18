from dataclasses import dataclass

from app.circuit_breaker import CircuitBreaker
from app.providers import ProviderConfig


@dataclass
class ProviderRuntime:
    config: ProviderConfig
    circuit_breaker: CircuitBreaker


def build_provider_runtimes(
    providers: list[ProviderConfig],
    failure_threshold: int,
    recovery_timeout: float,
) -> list[ProviderRuntime]:
    return [
        ProviderRuntime(
            config=provider,
            circuit_breaker=CircuitBreaker(
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
            ),
        )
        for provider in providers
    ]
