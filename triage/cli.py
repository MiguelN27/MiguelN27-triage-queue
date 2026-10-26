"""Text menu for operating the triage queue from a terminal."""

from typing import Callable, Optional

from .models import VALID_LEVELS, Patient, TriageLevel
from .queue import EmptyQueueError, TriageQueue

InputFn = Callable[[str], str]
OutputFn = Callable[..., None]

MENU = """
=== Emergency Triage Queue ===
1) Add a new patient
2) Call the next patient
3) View the current queue
4) See queue stats
5) Exit"""

LEVEL_PROMPT = "Triage level (1 = critical, 2 = urgent, 3 = standard): "


def level_label(level: int) -> str:
    return TriageLevel(level).name.capitalize()


def describe(patient: Patient) -> str:
    return (
        f"{patient.name} [{level_label(patient.triage_level)}], "
        f"arrived {patient.arrived_at:%H:%M:%S}"
    )


def run(
    queue: Optional[TriageQueue] = None,
    input_fn: InputFn = input,
    output: OutputFn = print,
) -> None:
    """Show the menu in a loop until the user exits.

    input_fn and output default to the terminal and can be swapped out to
    drive the menu from a script or a test.
    """
    # Compare against None: an empty queue has len 0 and is falsy.
    if queue is None:
        queue = TriageQueue()
    actions = {
        "1": _add_patient,
        "2": _call_next,
        "3": _show_queue,
        "4": _show_stats,
    }
    try:
        while True:
            output(MENU)
            choice = input_fn("Choose an option: ").strip()
            if choice == "5":
                break
            action = actions.get(choice)
            if action is None:
                output("Invalid option. Please choose 1-5.")
                continue
            action(queue, input_fn, output)
    except (EOFError, KeyboardInterrupt):
        # Ctrl-D / Ctrl-C (or the end of piped input) closes the menu
        # instead of crashing with a traceback.
        output()
    output("Goodbye.")


def _add_patient(queue: TriageQueue, input_fn: InputFn, output: OutputFn) -> None:
    name = _ask_name(input_fn, output)
    level = _ask_level(input_fn, output)
    patient = Patient(name, level)
    queue.enqueue(patient)
    output(f"Added {describe(patient)}.")


def _ask_name(input_fn: InputFn, output: OutputFn) -> str:
    while True:
        name = input_fn("Patient name: ").strip()
        if name:
            return name
        output("Name cannot be empty.")


def _ask_level(input_fn: InputFn, output: OutputFn) -> int:
    while True:
        raw = input_fn(LEVEL_PROMPT).strip()
        try:
            level = int(raw)
        except ValueError:
            level = None
        if level in VALID_LEVELS:
            return level
        output("Triage level must be 1, 2 or 3.")


def _call_next(queue: TriageQueue, input_fn: InputFn, output: OutputFn) -> None:
    # Dequeue directly instead of peek-then-dequeue, so the patient shown is
    # always the one actually removed from the queue.
    try:
        patient = queue.dequeue()
    except EmptyQueueError:
        output("No patients waiting.")
        return
    output(f"Now attending: {describe(patient)}.")


def _show_queue(queue: TriageQueue, input_fn: InputFn, output: OutputFn) -> None:
    patients = queue.list_queue()
    if not patients:
        output("Queue is empty.")
        return
    output("Waiting patients, in attention order:")
    for position, patient in enumerate(patients, start=1):
        output(f"{position:>3}. {describe(patient)}")


def _show_stats(queue: TriageQueue, input_fn: InputFn, output: OutputFn) -> None:
    counts = queue.stats()
    output("Patients waiting per triage level:")
    for level in TriageLevel:
        output(f"  {level_label(level):<8} ({level.value}): {counts[level.value]}")
    output(f"  {'Total':<12}: {sum(counts.values())}")
