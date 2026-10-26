"""Domain model for the emergency triage queue."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum


class TriageLevel(IntEnum):
    """Triage levels. A lower value means the patient is attended sooner."""

    CRITICAL = 1
    URGENT = 2
    STANDARD = 3


VALID_LEVELS = tuple(level.value for level in TriageLevel)


@dataclass(frozen=True)
class Patient:
    """A patient waiting in the emergency unit.

    The class is frozen so a patient's triage level can't change while they
    sit inside the queue, which would silently break the queue's ordering.
    """

    name: str
    triage_level: int
    arrived_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Patient name must be a non-empty string.")
        # bool is a subclass of int, so True would otherwise pass as level 1.
        if (
            not isinstance(self.triage_level, int)
            or isinstance(self.triage_level, bool)
            or self.triage_level not in VALID_LEVELS
        ):
            raise ValueError(
                f"Triage level must be one of {VALID_LEVELS}, "
                f"got {self.triage_level!r}."
            )
