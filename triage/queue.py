"""Priority queue that decides the order patients are attended in."""

import heapq
import itertools
import threading
from typing import Dict, List, Tuple

from .models import VALID_LEVELS, Patient

# Heap entry: (triage_level, arrival sequence number, patient).
# Tuples compare element by element, so the heap orders by triage level
# first and arrival order second. The sequence number is unique, so a
# comparison never reaches the Patient itself.
_Entry = Tuple[int, int, Patient]


class EmptyQueueError(IndexError):
    """Raised when asking for a patient while nobody is waiting."""


class TriageQueue:
    """Emergency unit waiting list.

    Patients are attended by triage level (1 before 2 before 3) and, within
    the same level, in arrival order (FIFO).
    """

    def __init__(self) -> None:
        self._heap: List[_Entry] = []
        self._counter = itertools.count()
        self._lock = threading.Lock()

    def __len__(self) -> int:
        with self._lock:
            return len(self._heap)

    def enqueue(self, patient: Patient) -> None:
        """Add a patient in their place by triage level and arrival order."""
        if not isinstance(patient, Patient):
            raise TypeError(f"Expected a Patient, got {type(patient).__name__}.")
        with self._lock:
            entry = (patient.triage_level, next(self._counter), patient)
            heapq.heappush(self._heap, entry)

    def dequeue(self) -> Patient:
        """Remove and return the next patient to be attended."""
        with self._lock:
            if not self._heap:
                raise EmptyQueueError("No patients waiting.")
            return heapq.heappop(self._heap)[2]

    def peek(self) -> Patient:
        """Return the next patient to be attended without removing them."""
        with self._lock:
            if not self._heap:
                raise EmptyQueueError("No patients waiting.")
            return self._heap[0][2]

    def list_queue(self) -> List[Patient]:
        """Return all waiting patients in the order they will be attended."""
        with self._lock:
            # sorted() works on a copy, so the heap itself is left untouched.
            return [patient for _, _, patient in sorted(self._heap)]

    def stats(self) -> Dict[int, int]:
        """Return how many patients are waiting at each triage level."""
        counts = {level: 0 for level in VALID_LEVELS}
        with self._lock:
            for level, _, _ in self._heap:
                counts[level] += 1
        return counts
