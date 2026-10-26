"""Emergency unit triage queue."""

from .models import Patient, TriageLevel
from .queue import EmptyQueueError, TriageQueue

__all__ = ["EmptyQueueError", "Patient", "TriageLevel", "TriageQueue"]
