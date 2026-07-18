"""Immutable window identity and geometry contracts."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WindowBounds:
    x: int
    y: int
    w: int
    h: int

    def as_dict(self) -> dict:
        return {"x": self.x, "y": self.y, "w": self.w, "h": self.h}


@dataclass(frozen=True)
class WindowIdentity:
    hwnd: int
    pid: int
    process_name: str
    process_path: str | None
    process_created: int | None
    class_name: str
    title: str
    owner_hwnd: int


@dataclass(frozen=True)
class WindowRef:
    identity: WindowIdentity
    outer: WindowBounds
    client: WindowBounds

    def as_dict(self) -> dict:
        return {
            **self.outer.as_dict(),
            "id": self.identity.hwnd,
            "pid": self.identity.pid,
            "process_name": self.identity.process_name,
            "process_path": self.identity.process_path,
            "process_created": self.identity.process_created,
            "class_name": self.identity.class_name,
            "title": self.identity.title,
            "owner_hwnd": self.identity.owner_hwnd,
            "client_rect": self.client.as_dict(),
        }


IDENTITY_KEYS = (
    "id", "pid", "process_name", "process_path", "process_created",
    "class_name", "title", "owner_hwnd"
)


def identity_matches(expected: dict, current: dict) -> bool:
    """Compare identity fields present in expected; legacy HWND-only refs still work."""
    return all(
        expected.get(key) is None or expected.get(key) == current.get(key)
        for key in IDENTITY_KEYS
    )
