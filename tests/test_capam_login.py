import unittest
from unittest.mock import patch

from core.capam_handler import CAPAMHandler


class _DeviceListAdapter:
    def get_window_rect(self, title, exact=False):
        if title == "Symantec Privileged Access Manager Client - 10.0.0.1" and exact:
            return {"id": 123}
        return None


class CAPAMLoginTests(unittest.TestCase):
    def test_device_list_is_positive_authenticated_state(self):
        handler = CAPAMHandler(_DeviceListAdapter(), "10.0.0.1")

        self.assertTrue(handler.wait_for_login_success(max_wait=1))

    def test_committed_login_does_not_type_or_submit_again(self):
        handler = CAPAMHandler(_DeviceListAdapter(), "10.0.0.1")
        rect = {"id": 123, "pid": 20, "process_created": 30}
        handler._actions.commit("capam_login_submit", rect)

        with patch("core.capam_handler.pyautogui.press") as press:
            self.assertTrue(handler.enter_credentials(rect, [(1, 2, 3, 4)], "user", "password"))

        press.assert_not_called()


if __name__ == "__main__":
    unittest.main()
