import unittest

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


if __name__ == "__main__":
    unittest.main()
