"""Priority queue that decides the order patients are attended in."""

import itertools
import threading
from typing import List, Tuple

from .models import Patient

# Heap entry: (triage_level, arrival sequence number, patient).
# Tuples compare element by element, so the heap orders by triage level
# first and arrival order second. The sequence number is unique, so a
# comparison never reaches the Patient itself.
_Entry = Tuple[int, int, Patient]


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
