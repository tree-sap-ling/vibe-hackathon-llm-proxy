import json
import os

from app.pii.models import PiiType
from app.pii.policy import ConsumerPolicy


PII_POLICIES_ENV = "PII_POLICIES_JSON"

_ALLOWED_KEYS = {
    "system_id",
    "enabled_types",
    "demask_enabled",
    "enabled",
}


def default_consumer_policies() -> tuple[ConsumerPolicy, ...]:
    all_types = frozenset(PiiType)

    return (
        ConsumerPolicy(
            system_id="autocheck",
            enabled_types=all_types,
            demask_enabled=True,
            enabled=True,
        ),
        ConsumerPolicy(
            system_id="llm-proxy",
            enabled_types=all_types,
            demask_enabled=True,
            enabled=True,
        ),
    )


def _parse_bool(
    item: dict,
    key: str,
    *,
    default: bool,
) -> bool:
    if key not in item:
        return default

    value = item[key]

    if not isinstance(value, bool):
        raise ValueError(
            f"{key} must be a JSON boolean"
        )

    return value


def _parse_enabled_types(value) -> frozenset[PiiType]:
    if not isinstance(value, list) or not value:
        raise ValueError(
            "enabled_types must be a non-empty JSON array"
        )

    if value == ["*"]:
        return frozenset(PiiType)

    if "*" in value:
        raise ValueError(
            'enabled_types wildcard "*" must be used alone'
        )

    parsed: set[PiiType] = set()

    for raw_type in value:
        if not isinstance(raw_type, str):
            raise ValueError(
                "enabled_types entries must be strings"
            )

        try:
            parsed.add(PiiType(raw_type))
        except ValueError as exc:
            raise ValueError(
                f"unknown PII type: {raw_type}"
            ) from exc

    return frozenset(parsed)


def parse_consumer_policies_json(
    raw: str,
) -> tuple[ConsumerPolicy, ...]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{PII_POLICIES_ENV} must be valid JSON"
        ) from exc

    if not isinstance(data, list) or not data:
        raise ValueError(
            f"{PII_POLICIES_ENV} must be a non-empty JSON array"
        )

    policies: list[ConsumerPolicy] = []
    seen_system_ids: set[str] = set()

    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(
                f"policy #{index + 1} must be a JSON object"
            )

        unknown_keys = set(item) - _ALLOWED_KEYS

        if unknown_keys:
            names = ", ".join(sorted(unknown_keys))
            raise ValueError(
                f"policy #{index + 1} has unknown fields: {names}"
            )

        system_id = item.get("system_id")

        if not isinstance(system_id, str):
            raise ValueError(
                f"policy #{index + 1} system_id must be a string"
            )

        if system_id in seen_system_ids:
            raise ValueError(
                f"duplicate system_id: {system_id}"
            )

        if "enabled_types" not in item:
            raise ValueError(
                f"policy {system_id!r} must define enabled_types"
            )

        policy = ConsumerPolicy(
            system_id=system_id,
            enabled_types=_parse_enabled_types(
                item["enabled_types"]
            ),
            demask_enabled=_parse_bool(
                item,
                "demask_enabled",
                default=True,
            ),
            enabled=_parse_bool(
                item,
                "enabled",
                default=True,
            ),
        )

        policies.append(policy)
        seen_system_ids.add(policy.system_id)

    return tuple(policies)


def get_consumer_policies() -> tuple[ConsumerPolicy, ...]:
    raw = os.getenv(PII_POLICIES_ENV)

    if raw is None or not raw.strip():
        return default_consumer_policies()

    return parse_consumer_policies_json(raw)
