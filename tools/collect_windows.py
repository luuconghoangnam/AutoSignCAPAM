"""Collect Windows metadata, window inventory and optional safe screenshots.

Examples:
    python -m tools.collect_windows --title "GlobalProtect" --capture --stage gp-portal
    python -m tools.collect_windows --title "Symantec Privileged Access Manager" --jab
    python -m tools.collect_windows --list-windows
"""
from __future__ import annotations

import argparse
import ctypes
import json
import platform
import sys
from pathlib import Path

from tools.common import capture_allowed, create_run_dir, require_windows, write_json


def list_windows() -> list[dict]:
    import pygetwindow as gw

    result = []
    for window in gw.getAllWindows():
        if window.width <= 0 or window.height <= 0 or not window.title.strip():
            continue
        hwnd = getattr(window, "_hWnd", None)
        pid, process_path = window_process(hwnd)
        result.append(
            {
                "title": window.title,
                "hwnd": hwnd,
                "pid": pid,
                "process_path": process_path,
                "x": window.left,
                "y": window.top,
                "width": window.width,
                "height": window.height,
                "minimized": bool(window.isMinimized),
            }
        )
    return result


def window_process(hwnd: int | None) -> tuple[int | None, str | None]:
    if not hwnd:
        return None, None
    try:
        pid = ctypes.c_ulong()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        process = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid.value)
        if not process:
            return pid.value, None
        try:
            buffer = ctypes.create_unicode_buffer(1024)
            size = ctypes.c_ulong(len(buffer))
            if ctypes.windll.kernel32.QueryFullProcessImageNameW(process, 0, buffer, ctypes.byref(size)):
                return pid.value, buffer.value
        finally:
            ctypes.windll.kernel32.CloseHandle(process)
        return pid.value, None
    except Exception:
        return None, None


def system_metadata() -> dict:
    metadata = {
        "platform": platform.platform(),
        "windows_version": platform.version(),
        "python": platform.python_version(),
        "machine": platform.machine(),
    }
    try:
        user32 = ctypes.windll.user32
        metadata["system_dpi"] = user32.GetDpiForSystem()
        metadata["foreground_hwnd"] = user32.GetForegroundWindow()
        metadata["screen"] = {
            "width": user32.GetSystemMetrics(0),
            "height": user32.GetSystemMetrics(1),
            "virtual_x": user32.GetSystemMetrics(76),
            "virtual_y": user32.GetSystemMetrics(77),
            "virtual_width": user32.GetSystemMetrics(78),
            "virtual_height": user32.GetSystemMetrics(79),
        }
    except Exception as exc:
        metadata["dpi_error"] = type(exc).__name__
    return metadata


def find_window(title: str) -> dict | None:
    matches = [item for item in list_windows() if item["title"] == title]
    if not matches:
        matches = [item for item in list_windows() if title.lower() in item["title"].lower()]
    return matches[0] if matches else None


def capture_window(window: dict, output: Path) -> None:
    from PIL import ImageGrab

    hwnd = window.get("hwnd")
    image = None
    if hwnd:
        try:
            image = ImageGrab.grab(window=hwnd, include_layered_windows=True)
        except Exception:
            image = None
    if image is None:
        image = ImageGrab.grab(
            bbox=(window["x"], window["y"], window["x"] + window["width"], window["y"] + window["height"])
        )
    image.save(output)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list-windows", action="store_true")
    parser.add_argument("--title", help="Exact or partial window title")
    parser.add_argument("--capture", action="store_true")
    parser.add_argument("--stage", default="unknown", help="Dataset label, e.g. gp-portal/device-list")
    parser.add_argument("--output", default="artifacts/diagnostics")
    parser.add_argument("--jab", action="store_true", help="Probe Java Access Bridge for target HWND")
    parser.add_argument("--allow-sensitive", action="store_true", help="Allow credential-stage screenshot")
    args = parser.parse_args(argv)
    require_windows()

    if args.list_windows:
        print(json.dumps(list_windows(), indent=2, ensure_ascii=True))
        return 0
    if not args.title:
        parser.error("--title required unless --list-windows is used")
    window = find_window(args.title)
    if not window:
        print(f"Window not found: {args.title}", file=sys.stderr)
        return 2

    if args.capture and not capture_allowed(args.stage, args.allow_sensitive):
        print("Refusing credential-stage screenshot. Add --allow-sensitive only after redaction review.", file=sys.stderr)
        return 3

    run_dir = create_run_dir(args.output)
    write_json(run_dir / "system.json", system_metadata())
    write_json(run_dir / "windows.json", {"target": window, "all_windows": list_windows()})
    if args.capture:
        capture_window(window, run_dir / f"{args.stage}.png")
    if args.jab:
        from tools.probe_jab import probe_jab

        write_json(run_dir / "jab.json", probe_jab(window["hwnd"]))
    from tools.probe_uia import probe_uia

    write_json(run_dir / "uia.json", probe_uia(window["hwnd"]))
    write_json(
        run_dir / "manifest.json",
        {
            "schema_version": 1,
            "stage": args.stage,
            "title": args.title,
            "hwnd": window["hwnd"],
            "sensitive_capture": bool(args.allow_sensitive),
        },
    )
    print(run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
