"""Collect Windows metadata, window inventory and optional safe screenshots.

Examples:
    python -m tools.collect_windows --title "GlobalProtect" --capture --stage gp-portal
    python -m tools.collect_windows --title "Symantec Privileged Access Manager" --jab
    python -m tools.collect_windows --list-windows
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path

from tools.common import capture_allowed, create_run_dir, require_windows, write_json


def list_windows() -> list[dict]:
    try:
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
    except (ImportError, ctypes.ArgumentError, TypeError):
        return _list_windows_win32()


def _list_windows_win32() -> list[dict]:
    """Fallback inventory when pygetwindow callback ABI is unavailable."""
    import win32gui

    result = []

    def visit(hwnd, _lparam):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        if not title:
            return
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        width, height = right - left, bottom - top
        if width <= 0 or height <= 0:
            return
        pid, process_path = window_process(hwnd)
        result.append(
            {
                "title": title,
                "hwnd": int(hwnd),
                "pid": pid,
                "process_path": process_path,
                "x": left,
                "y": top,
                "width": width,
                "height": height,
                "minimized": bool(win32gui.IsIconic(hwnd)),
            }
        )

    win32gui.EnumWindows(visit, None)
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


def _git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def _machine_id() -> str:
    # Stable anonymous identifier; never persist account or hostname.
    source = f"{platform.node()}|{platform.machine()}|{platform.platform()}"
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]


def _file_version(path: str | None) -> str | None:
    if not path or not Path(path).exists():
        return None
    try:
        from win32api import GetFileVersionInfo, HIWORD, LOWORD

        info = GetFileVersionInfo(path, "\\")
        ms = info["FileVersionMS"]
        ls = info["FileVersionLS"]
        return f"{HIWORD(ms)}.{LOWORD(ms)}.{HIWORD(ls)}.{LOWORD(ls)}"
    except (ImportError, OSError, KeyError, TypeError):
        return None


EXPECTED_STATE_BY_STAGE = {
    "gp-portal": "GP_DETECT",
    "gp-credentials": "GP_DETECT",
    "capam-address": "CAPAM_ADDRESS",
    "capam-login": "CAPAM_LOGIN",
    "device-list": "RDP_CLICK",
    "windows-security": "WINDOWS_SECURITY",
}


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


def capture_rect(hwnd: int | None) -> list[int] | None:
    if not hwnd:
        return None
    try:
        user32 = ctypes.windll.user32
        client = (ctypes.c_long * 4)()
        origin = (ctypes.c_long * 2)()
        if not user32.GetClientRect(hwnd, client) or not user32.ClientToScreen(hwnd, origin):
            return None
        return [origin[0], origin[1], client[2] - client[0], client[3] - client[1]]
    except Exception:
        return None


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
    system = system_metadata()
    write_json(run_dir / "system.json", system)
    write_json(run_dir / "windows.json", {"target": window})
    image_size = None
    if args.capture:
        capture_window(window, run_dir / f"{args.stage}.png")
        from PIL import Image

        with Image.open(run_dir / f"{args.stage}.png") as image:
            image_size = [image.width, image.height]
    if args.jab:
        from tools.probe_jab import probe_jab

        write_json(run_dir / "jab.json", probe_jab(window["hwnd"]))
    from tools.probe_uia import probe_uia

    write_json(run_dir / "uia.json", probe_uia(window["hwnd"]))
    write_json(
        run_dir / "manifest.json",
        {
            "schema_version": 1,
            "run_id": run_dir.name,
            "commit": _git_commit(),
            "machine_id": _machine_id(),
            "os": platform.system(),
            "os_build": system.get("windows_version"),
            "stage": args.stage,
            "expected_state": EXPECTED_STATE_BY_STAGE.get(args.stage),
            "title": args.title,
            "hwnd": window["hwnd"],
            "pid": window["pid"],
            "process_name": Path(window["process_path"]).name if window.get("process_path") else None,
            "process_path": window.get("process_path"),
            "app_version": _file_version(window.get("process_path")),
            "dpi": system.get("system_dpi"),
            "display_scale_percent": round((system.get("system_dpi") or 96) * 100 / 96),
            "text_scale_percent": None,
            "resolution": [system["screen"]["width"], system["screen"]["height"]],
            "monitor_index": None,
            "window_rect": [window["x"], window["y"], window["width"], window["height"]],
            "capture_rect": capture_rect(window["hwnd"]),
            "image_size": image_size,
            "contains_sensitive_data": bool(args.allow_sensitive),
            "sensitive_capture": bool(args.allow_sensitive),
        },
    )
    print(run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
