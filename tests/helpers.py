"""Shared helpers for the test suite."""

from triage import TriageQueue
from triage.cli import run


def queue_with(*patients):
    queue = TriageQueue()
    for patient in patients:
        queue.enqueue(patient)
    return queue


def drain(queue):
    """Dequeue every waiting patient and return their names in order."""
    return [queue.dequeue().name for _ in range(len(queue))]


class ScriptedSession:
    """Feeds scripted answers to the menu and records what it prints.

    Running out of answers behaves like the user pressing Ctrl-D.
    """

    def __init__(self, *answers):
        self._answers = iter(answers)
        self.lines = []

    def input(self, prompt=""):
        try:
            return next(self._answers)
        except StopIteration:
            raise EOFError from None

    def output(self, text=""):
        self.lines.append(str(text))

    def count(self, text):
        return sum(text in line for line in self.lines)

    def index_of(self, text):
        return next(i for i, line in enumerate(self.lines) if text in line)


def run_session(*answers, queue=None):
    session = ScriptedSession(*answers)
    queue = TriageQueue() if queue is None else queue
    run(queue, input_fn=session.input, output=session.output)
    return session, queue
