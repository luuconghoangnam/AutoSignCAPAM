"""Shared safe output helpers for Windows diagnostics tools."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


def create_run_dir(root: str = "artifacts/diagnostics") -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = Path(root) / stamp
    suffix = 1
    while path.exists():
        path = Path(root) / f"{stamp}-{suffix}"
        suffix += 1
    path.mkdir(parents=True)
    return path


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True), encoding="utf-8")


def require_windows() -> None:
    if os.name != "nt":
        raise SystemExit("This tool requires Windows.")


SENSITIVE_STAGES = {"gp-credentials", "capam-login", "windows-security"}


def capture_allowed(stage: str, allow_sensitive: bool) -> bool:
    return stage not in SENSITIVE_STAGES or allow_sensitive
