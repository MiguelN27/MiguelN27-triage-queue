import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime

from triage import Patient, TriageLevel, TriageQueue


class PatientTests(unittest.TestCase):
    def test_records_name_level_and_arrival(self):
        arrived = datetime(2026, 10, 25, 14, 30)
        patient = Patient("Ana", 2, arrived)

        self.assertEqual(patient.name, "Ana")
        self.assertEqual(patient.triage_level, 2)
        self.assertEqual(patient.arrived_at, arrived)

    def test_arrival_time_defaults_to_now(self):
        before = datetime.now()
        patient = Patient("Ana", 3)
        after = datetime.now()

        self.assertTrue(before <= patient.arrived_at <= after)

    def test_accepts_triage_level_enum(self):
        patient = Patient("Ana", TriageLevel.CRITICAL)

        self.assertEqual(patient.triage_level, 1)

    def test_rejects_invalid_triage_levels(self):
        for level in (0, 4, -1, "2", 2.0, None, True):
            with self.subTest(level=level):
                with self.assertRaises(ValueError):
                    Patient("Ana", level)

    def test_rejects_blank_names(self):
        for name in ("", "   ", None):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    Patient(name, 1)

    def test_triage_level_cannot_change_after_creation(self):
        patient = Patient("Ana", 3)

        with self.assertRaises(FrozenInstanceError):
            patient.triage_level = 1


class TriageQueueModelTests(unittest.TestCase):
    def test_new_queue_is_empty(self):
        self.assertEqual(len(TriageQueue()), 0)


if __name__ == "__main__":
    unittest.main()
