"""Capture exact window instances while keeping rect and pixels synchronized."""
from __future__ import annotations

from capture.frame import FrameSnapshot


class FrameCapture:
    def __init__(self, adapter):
        self.adapter = adapter

    def capture(self, rect: dict) -> FrameSnapshot | None:
        hwnd = rect.get("id")
        current = self.adapter.get_window_rect_for_hwnd(hwnd) if hwnd else rect.copy()
        if not current or (hwnd and current.get("id") != hwnd):
            return None
        image = self.adapter.capture_window(current)
        if image is None:
            return None
        image_h, image_w = image.shape[:2]
        capture_rect = current.copy()
        capture_rect["w"] = image_w
        capture_rect["h"] = image_h
        return FrameSnapshot.from_image(image, capture_rect)
