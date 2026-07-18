import unittest
from unittest.mock import patch

from core.action_transaction import ActionTransaction
from core.gp_handler import GPHandler


class _GPAdapter:
    def __init__(self):
        self.foreground = True
        self.controls = {}

    def is_foreground(self, rect):
        return self.foreground

    def focus_rect(self, rect):
        return True

    def get_window_rect_for_hwnd(self, hwnd):
        return {
            "id": hwnd,
            "pid": 20,
            "process_created": 30,
            "x": 1000,
            "y": 500,
            "w": 287,
            "h": 421,
            "client_rect": {"x": 1000, "y": 500, "w": 287, "h": 421},
        }

    def get_capture_rect_for_hwnd(self, hwnd):
        return {"x": 1000, "y": 500, "w": 287, "h": 421}

    def get_descendant_control_rect(self, rect, control_id):
        return self.controls.get(control_id)


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

    def test_single_credential_field_refills_both_credentials(self):
        handler = GPHandler(_GPAdapter())
        handler._last_capture_rect = {"x": 1000, "y": 500, "w": 287, "h": 421}
        rect = {
            "id": 10,
            "pid": 20,
            "process_created": 30,
            "x": 1000,
            "y": 500,
            "w": 287,
            "h": 421,
        }

        with (
            patch("core.gp_handler.pyautogui.click") as click,
            patch("core.gp_handler.pyautogui.moveTo") as move,
            patch("core.gp_handler.pyautogui.hotkey"),
            patch("core.gp_handler.pyautogui.press"),
            patch("core.gp_handler.write_text_safely", return_value=True) as write,
        ):
            self.assertTrue(
                handler.enter_credentials(
                    rect,
                    [(37, 339, 218, 35)],
                    "saved-user",
                    "password-otp",
                )
            )

        self.assertEqual(
            [call.args for call in move.call_args_list],
            [(1146, 802), (1146, 856)],
        )
        self.assertEqual(
            [call.kwargs for call in move.call_args_list],
            [{"duration": 0.25}, {"duration": 0.25}],
        )
        self.assertEqual(click.call_count, 2)
        self.assertEqual(
            [call.args[0] for call in write.call_args_list],
            ["saved-user", "password-otp"],
        )

    def test_credential_points_outside_client_are_rejected(self):
        handler = GPHandler(_GPAdapter())
        handler._last_capture_rect = {"x": 1000, "y": 500, "w": 287, "h": 421}
        rect = {
            "id": 10, "pid": 20, "process_created": 30,
            "x": 1000, "y": 500, "w": 287, "h": 421,
        }

        with (
            patch("core.gp_handler.pyautogui.moveTo") as move,
            patch("core.gp_handler.write_text_safely") as write,
        ):
            self.assertFalse(
                handler.enter_credentials(rect, [(37, 10, 218, 35)], "user", "secret")
            )

        move.assert_not_called()
        write.assert_not_called()

    def test_win32_edit_controls_override_opencv_connect_button(self):
        adapter = _GPAdapter()
        adapter.controls = {
            1166: {"x": 1038, "y": 741, "w": 216, "h": 28},
            1167: {"x": 1038, "y": 795, "w": 216, "h": 28},
        }
        handler = GPHandler(adapter)
        handler._last_capture_rect = {"x": 1000, "y": 500, "w": 287, "h": 421}
        rect = {
            "id": 10, "pid": 20, "process_created": 30,
            "x": 1000, "y": 500, "w": 287, "h": 421,
        }

        with (
            patch("core.gp_handler.pyautogui.click"),
            patch("core.gp_handler.pyautogui.moveTo") as move,
            patch("core.gp_handler.pyautogui.hotkey"),
            patch("core.gp_handler.pyautogui.press"),
            patch("core.gp_handler.write_text_safely", return_value=True),
        ):
            self.assertTrue(
                handler.enter_credentials(rect, [(37, 339, 218, 35)], "user", "secret")
            )

        self.assertEqual(
            [call.args[:2] for call in move.call_args_list],
            [(1146, 755), (1146, 809)],
        )


if __name__ == "__main__":
    unittest.main()
