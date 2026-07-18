import unittest
from unittest.mock import patch

from core.action_transaction import ActionTransaction
from core.gp_handler import GPHandler


class _GPAdapter:
    def __init__(self):
        self.foreground = True

    def is_foreground(self, rect):
        return self.foreground


class ActionTransactionTests(unittest.TestCase):
    def test_same_action_and_window_commits_once(self):
        actions = ActionTransaction()
        rect = {"id": 10, "pid": 20, "process_created": 30}

        self.assertTrue(actions.commit("submit", rect))
        self.assertFalse(actions.commit("submit", rect))
        self.assertTrue(actions.commit("other", rect))

    def test_new_process_generation_gets_new_transaction(self):
        actions = ActionTransaction()

        self.assertTrue(actions.commit("submit", {"id": 10, "pid": 20, "process_created": 30}))
        self.assertTrue(actions.commit("submit", {"id": 10, "pid": 20, "process_created": 31}))

    def test_gp_submit_sends_enter_once(self):
        handler = GPHandler(_GPAdapter())
        rect = {"id": 10, "pid": 20, "process_created": 30}

        with patch("core.gp_handler.pyautogui.press") as press:
            self.assertTrue(handler.submit_credentials(rect))
            self.assertTrue(handler.submit_credentials(rect))

        press.assert_called_once_with("enter")

    def test_precommit_focus_failure_remains_retryable(self):
        adapter = _GPAdapter()
        handler = GPHandler(adapter)
        rect = {"id": 10, "pid": 20, "process_created": 30}
        adapter.foreground = False

        with patch("core.gp_handler.pyautogui.press") as press:
            self.assertFalse(handler.submit_credentials(rect))
            adapter.foreground = True
            self.assertTrue(handler.submit_credentials(rect))

        press.assert_called_once_with("enter")


if __name__ == "__main__":
    unittest.main()
