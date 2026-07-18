import unittest

import numpy as np

from capture.window_capture import FrameCapture


class FakeAdapter:
    def __init__(self, image=None, current=None):
        self.image = image
        self.current = current

    def get_window_rect_for_hwnd(self, hwnd):
        return self.current

    def capture_window(self, rect):
        return self.image


class FrameCaptureTests(unittest.TestCase):
    def test_capture_uses_actual_image_dimensions(self):
        adapter = FakeAdapter(
            image=np.zeros((120, 240, 3), dtype=np.uint8),
            current={"id": 7, "x": 10, "y": 20, "w": 200, "h": 100},
        )
        snapshot = FrameCapture(adapter).capture({"id": 7})
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.rect["w"], 240)
        self.assertEqual(snapshot.rect["h"], 120)

    def test_capture_rejects_changed_window_identity(self):
        adapter = FakeAdapter(
            image=np.zeros((10, 10, 3), dtype=np.uint8),
            current={"id": 8, "w": 10, "h": 10},
        )
        self.assertIsNone(FrameCapture(adapter).capture({"id": 7}))


if __name__ == "__main__":
    unittest.main()
