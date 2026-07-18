"""Append-only, redacted JSONL timeline for runtime and monitor events."""
from __future__ import annotations

import json
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path


_SENSITIVE_KEYS = {"password", "password_prefix", "otp", "secret", "clipboard", "value"}
_OTP_PATTERN = re.compile(r"(?<!\d)\d{6}(?!\d)")


def redact(value, secrets: tuple[str, ...] = (), redact_otp: bool = True):
    if isinstance(value, dict):
        return {
            key: "<redacted>" if key.lower() in _SENSITIVE_KEYS else redact(item, secrets, redact_otp)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item, secrets, redact_otp) for item in value]
    if isinstance(value, tuple):
        return [redact(item, secrets, redact_otp) for item in value]
    if isinstance(value, str):
        result = value
        for secret in secrets:
            if secret:
                result = result.replace(secret, "<redacted>")
        return _OTP_PATTERN.sub("<redacted-otp>", result) if redact_otp else result
    return value


class TimelineWriter:
    def __init__(self, path: str | Path, source: str, session_id: str, secrets=(), redact_otp=True):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.source = source
        self.session_id = session_id
        self.secrets = tuple(secret for secret in secrets if secret)
        self.redact_otp = redact_otp
        self._sequence = 0
        self._lock = threading.Lock()

    def emit(self, event: str, **data) -> None:
        with self._lock:
            self._sequence += 1
            record = {
                "schema_version": 1,
                "session_id": self.session_id,
                "sequence": self._sequence,
                "source": self.source,
                "event": event,
                "utc": datetime.now(timezone.utc).isoformat(),
                "monotonic": time.monotonic(),
                "data": redact(data, self.secrets, self.redact_otp),
            }
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n")
