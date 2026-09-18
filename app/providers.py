import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    base_url: str
    api_key: str | None = None


def normalize_base_url(value: str) -> str:
    return value.strip().rstrip("/")


def get_provider_configs() -> list[ProviderConfig]:
    primary_url = normalize_base_url(
        os.getenv(
            "UPSTREAM_BASE_URL",
            "http://127.0.0.1:9000",
        )
    )

    primary = ProviderConfig(
        name="primary",
        base_url=primary_url,
        api_key=os.getenv("UPSTREAM_API_KEY") or None,
    )

    providers = [primary]

    fallback_url = normalize_base_url(
        os.getenv("FALLBACK_UPSTREAM_BASE_URL", "")
    )

    if fallback_url and fallback_url != primary_url:
        providers.append(
            ProviderConfig(
                name="fallback",
                base_url=fallback_url,
                api_key=(
                    os.getenv("FALLBACK_UPSTREAM_API_KEY")
                    or None
                ),
            )
        )

    return providers
