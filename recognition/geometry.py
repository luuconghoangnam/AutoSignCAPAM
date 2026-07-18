"""DPI-independent geometry helpers."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NormalizedBox:
    x: float
    y: float
    w: float
    h: float

    @property
    def center(self) -> tuple[float, float]:
        return self.x + self.w / 2, self.y + self.h / 2


def normalize_box(box: tuple[int, int, int, int], width: int, height: int) -> NormalizedBox:
    if width <= 0 or height <= 0:
        raise ValueError("Frame dimensions must be positive")
    x, y, w, h = box
    return NormalizedBox(x / width, y / height, w / width, h / height)


def normalize_point(point: tuple[int, int], width: int, height: int) -> tuple[float, float]:
    if width <= 0 or height <= 0:
        raise ValueError("Frame dimensions must be positive")
    return point[0] / width, point[1] / height


def to_screen_point(
    point: tuple[int, int],
    source_width: int,
    source_height: int,
    screen_rect: dict,
) -> tuple[int, int]:
    normalized_x, normalized_y = normalize_point(point, source_width, source_height)
    return (
        round(screen_rect["x"] + normalized_x * screen_rect["w"]),
        round(screen_rect["y"] + normalized_y * screen_rect["h"]),
    )


def boxes_stable(
    previous: list[tuple[int, int, int, int]],
    current: list[tuple[int, int, int, int]],
    width: int,
    height: int,
    center_tolerance: float = 0.012,
    size_tolerance: float = 0.05,
    previous_width: int | None = None,
    previous_height: int | None = None,
) -> bool:
    if len(previous) != len(current):
        return False
    previous_width = previous_width or width
    previous_height = previous_height or height
    for old_box, new_box in zip(previous, current):
        old = normalize_box(old_box, previous_width, previous_height)
        new = normalize_box(new_box, width, height)
        old_x, old_y = old.center
        new_x, new_y = new.center
        if abs(old_x - new_x) > center_tolerance or abs(old_y - new_y) > center_tolerance:
            return False
        if abs(old.w - new.w) > size_tolerance or abs(old.h - new.h) > size_tolerance:
            return False
    return True


def points_stable(
    previous: tuple[int, int] | None,
    current: tuple[int, int],
    width: int,
    height: int,
    tolerance: float = 0.012,
) -> bool:
    if previous is None:
        return False
    old_x, old_y = normalize_point(previous, width, height)
    new_x, new_y = normalize_point(current, width, height)
    return abs(old_x - new_x) <= tolerance and abs(old_y - new_y) <= tolerance
