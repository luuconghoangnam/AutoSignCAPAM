"""Capture exact window instances while keeping rect and pixels synchronized."""
from __future__ import annotations

from capture.frame import FrameSnapshot
from adapters.window_identity import identity_matches


def _rect_for_image(current: dict, client: dict | None, image_w: int, image_h: int) -> dict:
    """Choose screen origin whose dimensions best match captured HWND pixels."""
    if not client:
        return current.copy()
    outer_error = abs(current.get("w", 0) - image_w) + abs(current.get("h", 0) - image_h)
    client_error = abs(client.get("w", 0) - image_w) + abs(client.get("h", 0) - image_h)
    return (current if outer_error <= client_error else client).copy()


class FrameCapture:
    def __init__(self, adapter):
        self.adapter = adapter

    def capture(self, rect: dict) -> FrameSnapshot | None:
        hwnd = rect.get("id")
        current = self.adapter.get_window_rect_for_hwnd(hwnd) if hwnd else rect.copy()
        if not current or not identity_matches(rect, current):
            return None
        image = self.adapter.capture_window(current)
        if image is None:
            return None
        after = self.adapter.get_window_rect_for_hwnd(hwnd) if hwnd else current.copy()
        if not after or not identity_matches(current, after):
            return None
        image_h, image_w = image.shape[:2]
        get_capture_rect = getattr(self.adapter, "get_capture_rect_for_hwnd", None)
        client_rect = get_capture_rect(hwnd) if get_capture_rect and hwnd else None
        capture_rect = _rect_for_image(current, client_rect, image_w, image_h)
        if capture_rect.get("id") != current.get("id"):
            return None
        if any(after.get(key) != current.get(key) for key in ("x", "y", "w", "h")):
            return None
        capture_rect["w"] = image_w
        capture_rect["h"] = image_h
        return FrameSnapshot.from_image(image, capture_rect)
