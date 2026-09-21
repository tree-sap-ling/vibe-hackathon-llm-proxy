import re
import secrets
from dataclasses import dataclass

from app.pii.models import PiiEntity, PiiType


_TOKEN_PATTERN = re.compile(
    r"<PII:[a-z_]+:\d+:[0-9a-f]+>"
)


class MaskingVault:
    __slots__ = ("_values", "_namespace")

    def __init__(self, namespace: str):
        self._namespace = namespace
        self._values: dict[str, str] = {}

    def __len__(self) -> int:
        return len(self._values)

    def __repr__(self) -> str:
        return (
            f"MaskingVault(items={len(self._values)}, "
            "values=<redacted>)"
        )

    def make_token(
        self,
        pii_type: PiiType,
        index: int,
    ) -> str:
        return (
            f"<PII:{pii_type.value}:{index}:"
            f"{self._namespace}>"
        )

    def store(self, token: str, value: str) -> None:
        if token in self._values:
            raise ValueError("duplicate masking token")

        self._values[token] = value

    def demask(self, text: str) -> str:
        def replace(match: re.Match[str]) -> str:
            token = match.group(0)
            return self._values.get(token, token)

        return _TOKEN_PATTERN.sub(replace, text)


@dataclass(frozen=True, slots=True)
class MaskingResult:
    text: str
    vault: MaskingVault
    detected_types: tuple[PiiType, ...]
    entity_count: int


def _make_namespace(
    source_text: str,
    requested_namespace: str | None,
) -> str:
    if requested_namespace is not None:
        if not re.fullmatch(
            r"[0-9a-f]+",
            requested_namespace,
        ):
            raise ValueError(
                "token_namespace must contain lowercase hex digits"
            )

        if requested_namespace in source_text:
            raise ValueError(
                "token_namespace collides with source text"
            )

        return requested_namespace

    while True:
        namespace = secrets.token_hex(8)

        if namespace not in source_text:
            return namespace


def _validate_entities(
    text: str,
    entities: list[PiiEntity],
) -> None:
    previous_end = 0

    for entity in entities:
        if entity.start < previous_end:
            raise ValueError(
                "mask_text requires non-overlapping entities"
            )

        if entity.end > len(text):
            raise ValueError(
                "entity span is outside source text"
            )

        previous_end = entity.end


def mask_text(
    text: str,
    entities: list[PiiEntity],
    *,
    token_namespace: str | None = None,
) -> MaskingResult:
    ordered = sorted(
        entities,
        key=lambda entity: (
            entity.start,
            entity.end,
            entity.pii_type.value,
        ),
    )

    _validate_entities(text, ordered)

    namespace = _make_namespace(
        text,
        token_namespace,
    )
    vault = MaskingVault(namespace)

    counters: dict[PiiType, int] = {}
    detected_types = []
    detected_type_set = set()
    parts = []
    cursor = 0

    for entity in ordered:
        parts.append(text[cursor:entity.start])

        counters[entity.pii_type] = (
            counters.get(entity.pii_type, 0) + 1
        )

        token = vault.make_token(
            entity.pii_type,
            counters[entity.pii_type],
        )
        original_value = text[entity.start:entity.end]

        vault.store(token, original_value)
        parts.append(token)

        if entity.pii_type not in detected_type_set:
            detected_type_set.add(entity.pii_type)
            detected_types.append(entity.pii_type)

        cursor = entity.end

    parts.append(text[cursor:])

    return MaskingResult(
        text="".join(parts),
        vault=vault,
        detected_types=tuple(detected_types),
        entity_count=len(ordered),
    )
