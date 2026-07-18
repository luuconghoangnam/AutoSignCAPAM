import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from core.rdp_handler import RDPHandler


class _Adapter:
    def __init__(self):
        self.dialog = None

    def get_capam_dialog_rect(self):
        return self.dialog

    def get_window_rects(self, title, exact=False):
        return []

    def get_rdp_windows(self):
        return {}

    def get_window_rect(self, title, exact=False):
        return None


class _ClickAdapter(_Adapter):
    rect = {
        "id": 10,
        "x": 100,
        "y": 100,
        "w": 400,
        "h": 300,
        "process_name": "CAPAMClient.exe",
    }

    def get_window_rect_for_hwnd(self, hwnd):
        return self.rect.copy()

    def is_foreground(self, rect):
        return True

    def focus_rect(self, rect):
        return True

    def wait_focus_rect(self, rect, timeout=5.0):
        return True

    def refresh_window(self, rect):
        return True

    def suppress_browser_foreground(self):
        return False

    def get_window_rects(self, title, exact=False):
        return []

    def get_rdp_windows(self):
        return {}


class RDPClickTests(unittest.TestCase):
    def test_click_requires_new_postcondition(self):
        adapter = _Adapter()
        handler = RDPHandler(adapter)
        context = {"auth_hwnds": set(), "rdp_windows": {}, "session": None}

        self.assertFalse(handler._click_started_rdp(context, "RDP-211.200"))
        adapter.dialog = {"id": 123}
        self.assertTrue(handler._click_started_rdp(context, "RDP-211.200"))

    def test_adapter_contract_does_not_click_desktop_by_default(self):
        from adapters.base import OSAdapter

        self.assertFalse(OSAdapter().click_window_point({"id": 1}, 10, 20))

    def test_rdp_action_is_clicked_at_most_once_without_postcondition(self):
        adapter = _ClickAdapter()
        handler = RDPHandler(adapter)
        image = np.zeros((300, 400, 3), dtype=np.uint8)
        snapshot = SimpleNamespace(
            image=image,
            rect=adapter.rect.copy(),
            is_blank=False,
            mean_delta=lambda previous: 0.0,
        )
        clock = [0.0]

        def monotonic():
            return clock[0]

        def sleep(seconds):
            clock[0] += seconds

        with (
            patch.object(handler._capture, "capture", return_value=snapshot),
            patch("core.rdp_handler.find_device_rdp_button", return_value={
                "point": (200, 150), "device_score": 0.9, "rdp_score": 0.9,
            }),
            patch("core.rdp_handler.time.monotonic", side_effect=monotonic),
            patch("core.rdp_handler.time.sleep", side_effect=sleep),
            patch("core.rdp_handler.pyautogui.click") as click,
        ):
            self.assertFalse(
                handler.click_rdp("200", "10.0.0.1", expected_rect=adapter.rect)
            )

        click.assert_called_once()

    def test_rdp_waits_for_slow_dialog_without_clicking_twice(self):
        adapter = _ClickAdapter()
        handler = RDPHandler(adapter)
        image = np.zeros((300, 400, 3), dtype=np.uint8)
        snapshot = SimpleNamespace(
            image=image,
            rect=adapter.rect.copy(),
            is_blank=False,
            mean_delta=lambda previous: 0.0,
        )
        clock = [0.0]

        def monotonic():
            return clock[0]

        def sleep(seconds):
            clock[0] += seconds

        adapter.get_capam_dialog_rect = lambda: (
            {"id": 123, "process_name": "CAPAMClient.exe"}
            if clock[0] >= 8.0 else None
        )
        with (
            patch.object(handler._capture, "capture", return_value=snapshot),
            patch("core.rdp_handler.find_device_rdp_button", return_value={
                "point": (200, 150), "device_score": 0.9, "rdp_score": 0.9,
            }),
            patch("core.rdp_handler.time.monotonic", side_effect=monotonic),
            patch("core.rdp_handler.time.sleep", side_effect=sleep),
            patch("core.rdp_handler.pyautogui.click") as click,
        ):
            self.assertTrue(
                handler.click_rdp("200", "10.0.0.1", expected_rect=adapter.rect)
            )

        click.assert_called_once()
        self.assertGreaterEqual(clock[0], 8.0)


if __name__ == "__main__":
    unittest.main()
