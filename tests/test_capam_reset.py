import unittest

from core.state_machine import AutomationWorker


class _Adapter:
    def __init__(self, running_states, kill_result=True):
        self.running_states = iter(running_states)
        self.current = True
        self.kill_result = kill_result
        self.killed = 0

    def is_capam_running(self):
        try:
            self.current = next(self.running_states)
        except StopIteration:
            pass
        return self.current

    def kill_capam(self):
        self.killed += 1
        return self.kill_result


class CAPAMResetTests(unittest.TestCase):
    def _worker(self, adapter):
        worker = AutomationWorker.__new__(AutomationWorker)
        worker._adapter = adapter
        worker._log = lambda message: None
        return worker

    def test_hidden_capam_process_is_killed_without_main_window(self):
        adapter = _Adapter([True, False])

        self.assertEqual(self._worker(adapter)._state_reset_capam(), "CHECK_VPN")
        self.assertEqual(adapter.killed, 1)

    def test_no_capam_process_skips_kill(self):
        adapter = _Adapter([False])

        self.assertEqual(self._worker(adapter)._state_reset_capam(), "CHECK_VPN")
        self.assertEqual(adapter.killed, 0)

    def test_failed_kill_stops_before_new_launch(self):
        adapter = _Adapter([True], kill_result=False)

        self.assertEqual(self._worker(adapter)._state_reset_capam(), "ERROR")
        self.assertEqual(adapter.killed, 1)


if __name__ == "__main__":
    unittest.main()
