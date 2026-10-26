"""One group of tests per item in the "Correctness and edge cases" checklist."""

import random
import sys
import threading
import unittest
from datetime import datetime
from functools import partial

from tests.helpers import drain, queue_with, run_session
from triage import EmptyQueueError, Patient, TriageQueue


def names(patients):
    return [patient.name for patient in patients]


class CriticalArrivalTests(unittest.TestCase):
    """A new level-1 patient goes ahead of waiting level-2 and level-3 patients."""

    def test_critical_patient_goes_ahead_of_urgent_and_standard(self):
        queue = queue_with(
            Patient("Ana", 3),
            Patient("Beto", 2),
            Patient("Carla", 3),
            Patient("Diego", 2),
        )

        queue.enqueue(Patient("Elena", 1))

        self.assertEqual(queue.peek().name, "Elena")
        self.assertEqual(
            names(queue.list_queue()), ["Elena", "Beto", "Diego", "Ana", "Carla"]
        )

    def test_critical_patient_arriving_mid_processing_is_next(self):
        queue = queue_with(Patient("Ana", 3), Patient("Beto", 2), Patient("Carla", 3))
        self.assertEqual(queue.dequeue().name, "Beto")

        queue.enqueue(Patient("Diego", 1))

        self.assertEqual(drain(queue), ["Diego", "Ana", "Carla"])

    def test_critical_patient_waits_behind_earlier_critical_patients(self):
        queue = queue_with(Patient("First", 1), Patient("Ana", 3))

        queue.enqueue(Patient("Second", 1))

        self.assertEqual(drain(queue), ["First", "Second", "Ana"])


class ArrivalOrderTests(unittest.TestCase):
    """Patients at the same triage level are attended in strict arrival order."""

    def test_same_level_patients_are_attended_in_arrival_order(self):
        arrivals = ["Ana", "Beto", "Carla", "Diego", "Elena", "Fabio"]
        queue = queue_with(*(Patient(name, 2) for name in arrivals))

        self.assertEqual(drain(queue), arrivals)

    def test_identical_arrival_times_still_keep_arrival_order(self):
        # Equal timestamps can't break the tie. The queue's own arrival
        # counter does, and it never lets the heap compare Patient objects.
        same_instant = datetime(2026, 10, 25, 9, 0)
        arrivals = ["Ana", "Beto", "Carla", "Diego", "Elena"]
        queue = queue_with(*(Patient(name, 2, same_instant) for name in arrivals))

        self.assertEqual(names(queue.list_queue()), arrivals)
        self.assertEqual(drain(queue), arrivals)

    def test_matches_reference_order_under_random_operations(self):
        # A plain list re-sorted on every step is slow but obviously correct.
        # The queue must agree with it after any mix of enqueues and dequeues.
        rng = random.Random(27)
        queue = TriageQueue()
        expected = []  # (triage_level, arrival step, name)

        for step in range(2000):
            if expected and rng.random() < 0.4:
                next_up = min(expected)
                expected.remove(next_up)
                self.assertEqual(queue.dequeue().name, next_up[2])
            else:
                level = rng.randint(1, 3)
                name = f"patient-{step}"
                queue.enqueue(Patient(name, level))
                expected.append((level, step, name))

        expected_order = [name for _, _, name in sorted(expected)]
        expected_stats = {
            level: sum(entry[0] == level for entry in expected) for level in (1, 2, 3)
        }
        self.assertEqual(names(queue.list_queue()), expected_order)
        self.assertEqual(queue.stats(), expected_stats)


class EmptyQueueTests(unittest.TestCase):
    """dequeue() and peek() on an empty queue don't crash the program."""

    def test_dequeue_raises_a_meaningful_error(self):
        with self.assertRaisesRegex(EmptyQueueError, "No patients waiting"):
            TriageQueue().dequeue()

    def test_peek_raises_a_meaningful_error(self):
        with self.assertRaisesRegex(EmptyQueueError, "No patients waiting"):
            TriageQueue().peek()

    def test_queue_keeps_working_after_the_error(self):
        queue = TriageQueue()
        with self.assertRaises(EmptyQueueError):
            queue.dequeue()
        with self.assertRaises(EmptyQueueError):
            queue.peek()

        queue.enqueue(Patient("Ana", 2))

        self.assertEqual(queue.peek().name, "Ana")
        self.assertEqual(queue.dequeue().name, "Ana")
        with self.assertRaises(EmptyQueueError):
            queue.dequeue()

    def test_menu_keeps_running_when_the_queue_is_empty(self):
        session, queue = run_session(
            "2", "2", "3", "4",   # call twice, view and stats while empty
            "1", "Ana", "1",      # then a patient arrives
            "2", "2", "5",        # attend them, then call on an empty queue again
        )

        self.assertEqual(session.count("No patients waiting."), 3)
        self.assertEqual(session.count("Now attending: Ana"), 1)
        self.assertEqual(session.lines[-1], "Goodbye.")
        self.assertEqual(len(queue), 0)


class ConcurrencyTests(unittest.TestCase):
    """Several nurses using the same queue at once never lose or repeat a patient."""

    TIMEOUT = 10

    def setUp(self):
        # Switch threads far more often than CPython's 5 ms default, so a
        # missing lock shows up as a failure instead of passing by luck.
        self.addCleanup(sys.setswitchinterval, sys.getswitchinterval())
        sys.setswitchinterval(1e-6)
        self.worker_errors = []

    def start_workers(self, *targets):
        """Start one thread per target, collecting any exception it raises."""

        def guarded(target):
            def runner():
                try:
                    target()
                except Exception as exc:
                    self.worker_errors.append(exc)

            return runner

        threads = [threading.Thread(target=guarded(target)) for target in targets]
        for thread in threads:
            thread.start()
        return threads

    def finish(self, threads):
        for thread in threads:
            thread.join(self.TIMEOUT)
        self.assertFalse(any(thread.is_alive() for thread in threads), "a worker hung")

    def test_concurrent_workers_never_lose_or_repeat_a_patient(self):
        queue = TriageQueue()
        producers, consumers, per_producer = 4, 4, 250
        expected = {f"p{w}-{i}" for w in range(producers) for i in range(per_producer)}
        start = threading.Barrier(producers + consumers, timeout=self.TIMEOUT)
        producers_done = threading.Event()
        attended = [[] for _ in range(consumers)]

        def produce(worker):
            start.wait()
            for i in range(per_producer):
                queue.enqueue(Patient(f"p{worker}-{i}", i % 3 + 1))

        def consume(results):
            start.wait()
            while True:
                # Read the flag before trying to dequeue: if producers were
                # already done and the queue is empty, nothing else will arrive.
                finished = producers_done.is_set()
                try:
                    results.append(queue.dequeue().name)
                except EmptyQueueError:
                    if finished:
                        return

        producer_threads = self.start_workers(
            *(partial(produce, worker) for worker in range(producers))
        )
        consumer_threads = self.start_workers(
            *(partial(consume, results) for results in attended)
        )
        self.finish(producer_threads)
        producers_done.set()
        self.finish(consumer_threads)

        self.assertEqual(self.worker_errors, [])
        all_attended = [name for results in attended for name in results]
        self.assertEqual(
            len(all_attended), len(expected), "a patient was lost or repeated"
        )
        self.assertEqual(set(all_attended), expected)
        self.assertEqual(queue.stats(), {1: 0, 2: 0, 3: 0})

    def test_critical_arrival_racing_a_dequeue_is_never_skipped(self):
        # Whichever operation wins the race, the outcome must be one of the
        # two valid orders: never a lost patient or a corrupted heap.
        for _ in range(200):
            queue = queue_with(Patient("Ana", 3), Patient("Beto", 2))
            start = threading.Barrier(2, timeout=self.TIMEOUT)
            attended = []

            def call_next():
                start.wait()
                attended.append(queue.dequeue().name)

            def critical_arrives():
                start.wait()
                queue.enqueue(Patient("Critical", 1))

            self.finish(self.start_workers(call_next, critical_arrives))

            self.assertEqual(self.worker_errors, [])
            waiting = names(queue.list_queue())
            if attended == ["Critical"]:
                self.assertEqual(waiting, ["Beto", "Ana"])
            else:
                self.assertEqual(attended, ["Beto"])
                self.assertEqual(waiting, ["Critical", "Ana"])


if __name__ == "__main__":
    unittest.main()
