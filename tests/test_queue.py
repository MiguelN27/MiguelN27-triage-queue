import unittest

from tests.helpers import drain, queue_with
from triage import EmptyQueueError, Patient, TriageQueue


class EnqueueTests(unittest.TestCase):
    def test_adds_patient_to_queue(self):
        queue = queue_with(Patient("Ana", 3))

        self.assertEqual(len(queue), 1)

    def test_rejects_anything_that_is_not_a_patient(self):
        queue = TriageQueue()
        for item in ("Ana", None, ("Ana", 1)):
            with self.subTest(item=item):
                with self.assertRaises(TypeError):
                    queue.enqueue(item)
        self.assertEqual(len(queue), 0)


class DequeueTests(unittest.TestCase):
    def test_serves_lower_triage_level_first(self):
        queue = queue_with(
            Patient("Standard", 3), Patient("Critical", 1), Patient("Urgent", 2)
        )

        self.assertEqual(drain(queue), ["Critical", "Urgent", "Standard"])

    def test_serves_same_level_in_arrival_order(self):
        queue = queue_with(Patient("Ana", 2), Patient("Beto", 2), Patient("Carla", 2))

        self.assertEqual(drain(queue), ["Ana", "Beto", "Carla"])

    def test_orders_by_level_then_arrival(self):
        queue = queue_with(
            Patient("Ana", 3),
            Patient("Beto", 2),
            Patient("Carla", 1),
            Patient("Diego", 3),
            Patient("Elena", 1),
            Patient("Fabio", 2),
        )

        self.assertEqual(
            drain(queue), ["Carla", "Elena", "Beto", "Fabio", "Ana", "Diego"]
        )

    def test_removes_the_patient(self):
        queue = queue_with(Patient("Ana", 1), Patient("Beto", 2))

        queue.dequeue()

        self.assertEqual(len(queue), 1)

    def test_empty_queue_raises_empty_queue_error(self):
        with self.assertRaises(EmptyQueueError):
            TriageQueue().dequeue()

    def test_empty_queue_error_is_an_index_error(self):
        with self.assertRaises(IndexError):
            TriageQueue().dequeue()


class PeekTests(unittest.TestCase):
    def test_returns_next_patient_without_removing_them(self):
        queue = queue_with(Patient("Ana", 3), Patient("Beto", 1))

        first_look = queue.peek()
        second_look = queue.peek()

        self.assertEqual(first_look.name, "Beto")
        self.assertIs(first_look, second_look)
        self.assertEqual(len(queue), 2)
        self.assertIs(queue.dequeue(), first_look)

    def test_empty_queue_raises_empty_queue_error(self):
        with self.assertRaises(EmptyQueueError):
            TriageQueue().peek()


class ListQueueTests(unittest.TestCase):
    def setUp(self):
        self.queue = queue_with(
            Patient("Ana", 3),
            Patient("Beto", 1),
            Patient("Carla", 2),
            Patient("Diego", 1),
        )

    def test_returns_patients_in_attention_order(self):
        names = [patient.name for patient in self.queue.list_queue()]

        self.assertEqual(names, ["Beto", "Diego", "Carla", "Ana"])

    def test_matches_dequeue_order_and_leaves_queue_unchanged(self):
        listed = [patient.name for patient in self.queue.list_queue()]

        self.assertEqual(len(self.queue), 4)
        self.assertEqual(drain(self.queue), listed)

    def test_empty_queue_returns_empty_list(self):
        self.assertEqual(TriageQueue().list_queue(), [])


class StatsTests(unittest.TestCase):
    def test_empty_queue_reports_zero_for_every_level(self):
        self.assertEqual(TriageQueue().stats(), {1: 0, 2: 0, 3: 0})

    def test_counts_waiting_patients_per_level(self):
        queue = queue_with(
            Patient("Ana", 3), Patient("Beto", 1), Patient("Carla", 3)
        )

        self.assertEqual(queue.stats(), {1: 1, 2: 0, 3: 2})

    def test_updates_after_dequeue(self):
        queue = queue_with(Patient("Ana", 3), Patient("Beto", 1))

        queue.dequeue()

        self.assertEqual(queue.stats(), {1: 0, 2: 0, 3: 1})


if __name__ == "__main__":
    unittest.main()
