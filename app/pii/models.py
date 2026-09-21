from dataclasses import dataclass
from enum import Enum


class PiiType(str, Enum):
    EMAIL = "email"
    PHONE = "phone"
    INN = "inn"
    BANK_CARD = "bank_card"
    PASSPORT_RF = "passport_rf"
    SUBDIVISION_CODE = "subdivision_code"
    BIRTH_DATE = "birth_date"
    PASSPORT_ISSUE_DATE = "passport_issue_date"
    DRIVER_LICENSE = "driver_license"
    CVV = "cvv"
    PIN = "pin"


@dataclass(frozen=True, slots=True)
class PiiEntity:
    pii_type: PiiType
    start: int
    end: int
    confidence: float = 1.0

    def __post_init__(self):
        if self.start < 0:
            raise ValueError("start must be non-negative")

        if self.end <= self.start:
            raise ValueError("end must be greater than start")

        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")

    def overlaps(self, other: "PiiEntity") -> bool:
        return self.start < other.end and other.start < self.end
