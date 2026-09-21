from dataclasses import dataclass

from app.pii.models import PiiType


class PolicyError(Exception):
    """Base class for consumer policy errors."""


class UnknownConsumerError(PolicyError):
    """Raised when a consumer is not configured."""


class ConsumerDisabledError(PolicyError):
    """Raised when a configured consumer is disabled."""


@dataclass(frozen=True, slots=True)
class ConsumerPolicy:
    system_id: str
    enabled_types: frozenset[PiiType]
    demask_enabled: bool = True
    enabled: bool = True

    def __post_init__(self):
        normalized = self.system_id.strip()

        if not normalized:
            raise ValueError("system_id must not be empty")

        if normalized != self.system_id:
            raise ValueError(
                "system_id must not contain surrounding whitespace"
            )


class PolicyRegistry:
    def __init__(
        self,
        policies: tuple[ConsumerPolicy, ...] = (),
    ):
        self._policies: dict[str, ConsumerPolicy] = {}

        for policy in policies:
            self.register(policy)

    def register(self, policy: ConsumerPolicy) -> None:
        if policy.system_id in self._policies:
            raise ValueError(
                f"duplicate system_id: {policy.system_id}"
            )

        self._policies[policy.system_id] = policy

    def get(self, system_id: str) -> ConsumerPolicy:
        try:
            return self._policies[system_id]
        except KeyError as exc:
            raise UnknownConsumerError(
                "consumer is not configured"
            ) from exc

    def get_authorized(
        self,
        system_id: str,
    ) -> ConsumerPolicy:
        policy = self.get(system_id)

        if not policy.enabled:
            raise ConsumerDisabledError(
                "consumer is disabled"
            )

        return policy

    def __len__(self) -> int:
        return len(self._policies)
