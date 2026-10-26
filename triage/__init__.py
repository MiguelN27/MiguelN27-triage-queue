"""Emergency unit triage queue."""

from .models import Patient, TriageLevel
from .queue import TriageQueue

__all__ = ["Patient", "TriageLevel", "TriageQueue"]
