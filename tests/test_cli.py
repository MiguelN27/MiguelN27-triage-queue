import unittest

from tests.helpers import run_session
from triage import TriageQueue
from triage.cli import run


class AddPatientTests(unittest.TestCase):
    def test_adds_patient_with_name_and_level(self):
        session, queue = run_session("1", "Ana", "3", "5")

        self.assertEqual(len(queue), 1)
        self.assertEqual(queue.peek().name, "Ana")
        self.assertEqual(queue.peek().triage_level, 3)
        self.assertEqual(session.count("Added Ana [Standard]"), 1)

    def test_blank_name_asks_again(self):
        session, queue = run_session("1", "", "   ", "Ana", "2", "5")

        self.assertEqual(session.count("Name cannot be empty."), 2)
        self.assertEqual(queue.peek().name, "Ana")

    def test_invalid_level_asks_again(self):
        session, queue = run_session("1", "Ana", "0", "4", "x", "", "2.5", "2", "5")

        self.assertEqual(session.count("Triage level must be 1, 2 or 3."), 5)
        self.assertEqual(queue.peek().triage_level, 2)


class CallNextTests(unittest.TestCase):
    def test_attends_highest_priority_patient(self):
        session, queue = run_session("1", "Ana", "3", "1", "Beto", "1", "2", "5")

        self.assertEqual(session.count("Now attending: Beto [Critical]"), 1)
        self.assertEqual([p.name for p in queue.list_queue()], ["Ana"])

    def test_empty_queue_does_not_crash(self):
        session, _ = run_session("2", "5")

        self.assertEqual(session.count("No patients waiting."), 1)
        self.assertEqual(session.lines[-1], "Goodbye.")


class ViewQueueTests(unittest.TestCase):
    def test_lists_patients_in_attention_order(self):
        session, _ = run_session(
            "1", "Ana", "3", "1", "Beto", "1", "1", "Carla", "2", "3", "5"
        )

        self.assertEqual(session.count("1. Beto [Critical]"), 1)
        self.assertLess(session.index_of("1. Beto"), session.index_of("2. Carla"))
        self.assertLess(session.index_of("2. Carla"), session.index_of("3. Ana"))

    def test_empty_queue_says_so(self):
        session, _ = run_session("3", "5")

        self.assertEqual(session.count("Queue is empty."), 1)


class StatsTests(unittest.TestCase):
    def test_shows_count_per_level_and_total(self):
        session, _ = run_session(
            "1", "Ana", "3", "1", "Beto", "1", "1", "Carla", "3", "4", "5"
        )

        self.assertIn("  Critical (1): 1", session.lines)
        self.assertIn("  Urgent   (2): 0", session.lines)
        self.assertIn("  Standard (3): 2", session.lines)
        self.assertIn("  Total       : 3", session.lines)


class MenuTests(unittest.TestCase):
    def test_invalid_option_shows_menu_again(self):
        session, _ = run_session("9", "abc", "5")

        self.assertEqual(session.count("Invalid option. Please choose 1-5."), 2)
        self.assertEqual(session.count("=== Emergency Triage Queue ==="), 3)

    def test_exit_option_ends_the_loop(self):
        session, _ = run_session("5", "1", "Ana", "1")

        self.assertEqual(session.lines[-1], "Goodbye.")
        self.assertEqual(session.count("=== Emergency Triage Queue ==="), 1)

    def test_end_of_input_exits_cleanly(self):
        # Input runs out halfway through adding a patient.
        session, queue = run_session("1", "Ana")

        self.assertEqual(session.lines[-1], "Goodbye.")
        self.assertEqual(len(queue), 0)

    def test_ctrl_c_exits_cleanly(self):
        def interrupt(prompt=""):
            raise KeyboardInterrupt

        lines = []
        run(TriageQueue(), input_fn=interrupt, output=lambda text="": lines.append(text))

        self.assertEqual(lines[-1], "Goodbye.")


if __name__ == "__main__":
    unittest.main()
