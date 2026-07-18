"""One-shot guards for non-idempotent UI actions."""
from __future__ import annotations


class ActionTransaction:
    """Allow each action once per exact window identity during one run."""

    def __init__(self):
        self._committed: set[tuple] = set()

    @staticmethod
    def _key(action: str, rect: dict) -> tuple:
        return (
            action,
            rect.get("id"),
            rect.get("pid"),
            rect.get("process_created"),
            rect.get("process_name"),
        )

    def is_committed(self, action: str, rect: dict) -> bool:
        return self._key(action, rect) in self._committed

    def commit(self, action: str, rect: dict) -> bool:
        """Commit action; False means same target already committed."""
        key = self._key(action, rect)
        if key in self._committed:
            return False
        self._committed.add(key)
        return True
