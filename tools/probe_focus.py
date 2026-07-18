"""Diagnose Windows foreground, Z-order, overlap and focus rebound without clicking."""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import time
from ctypes import wintypes

import win32api
import win32con
import win32gui
import win32process


GWL_EXSTYLE = -20
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
WS_EX_NOACTIVATE = 0x08000000
DWMWA_CLOAKED = 14


def _process_name(pid: int) -> str | None:
    handle = None
    try:
        handle = win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        return os.path.basename(win32process.GetModuleFileNameEx(handle, 0))
    except Exception:
        return None
    finally:
        if handle:
            handle.Close()


def _cloaked(hwnd: int) -> bool | None:
    value = wintypes.DWORD()
    try:
        result = ctypes.windll.dwmapi.DwmGetWindowAttribute(
            hwnd, DWMWA_CLOAKED, ctypes.byref(value), ctypes.sizeof(value)
        )
        return bool(value.value) if result == 0 else None
    except Exception:
        return None


def window_info(hwnd: int, z_index: int | None = None) -> dict:
    thread_id, pid = win32process.GetWindowThreadProcessId(hwnd)
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    exstyle = win32gui.GetWindowLong(hwnd, GWL_EXSTYLE)
    return {
        "hwnd": int(hwnd),
        "pid": pid,
        "thread_id": thread_id,
        "process_name": _process_name(pid),
        "title": win32gui.GetWindowText(hwnd),
        "class_name": win32gui.GetClassName(hwnd),
        "rect": [left, top, right - left, bottom - top],
        "z_index": z_index,
        "visible": bool(win32gui.IsWindowVisible(hwnd)),
        "enabled": bool(win32gui.IsWindowEnabled(hwnd)),
        "minimized": bool(win32gui.IsIconic(hwnd)),
        "owner_hwnd": int(win32gui.GetWindow(hwnd, win32con.GW_OWNER) or 0),
        "topmost": bool(exstyle & WS_EX_TOPMOST),
        "no_activate": bool(exstyle & WS_EX_NOACTIVATE),
        "tool_window": bool(exstyle & WS_EX_TOOLWINDOW),
        "app_window": bool(exstyle & WS_EX_APPWINDOW),
        "cloaked": _cloaked(hwnd),
    }


def snapshot() -> dict:
    windows = []

    def visit(hwnd, _):
        if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
            windows.append(window_info(hwnd, len(windows)))

    win32gui.EnumWindows(visit, None)
    foreground = win32gui.GetForegroundWindow()
    return {
        "utc_epoch": time.time(),
        "foreground": window_info(foreground) if foreground else None,
        "windows": windows,
    }


def _overlap(first: list[int], second: list[int]) -> int:
    ax, ay, aw, ah = first
    bx, by, bw, bh = second
    return max(0, min(ax + aw, bx + bw) - max(ax, bx)) * max(
        0, min(ay + ah, by + bh) - max(ay, by)
    )


def relevant(snapshot_value: dict) -> dict:
    names = {
        "autosigncapam.exe", "python.exe", "pangpa.exe", "capamclient.exe",
        "mstsc.exe", "brave.exe", "chrome.exe", "msedge.exe",
    }
    windows = [
        item for item in snapshot_value["windows"]
        if (item.get("process_name") or "").lower() in names
        or item["title"] in ("CAPAM AutoSign", "GlobalProtect", "Windows Security")
        or "Privileged Access Manager" in item["title"]
    ]
    tool = next((item for item in windows if item["title"] == "CAPAM AutoSign"), None)
    if tool:
        for item in windows:
            item["overlap_with_tool_px2"] = _overlap(tool["rect"], item["rect"])
    return {"foreground": snapshot_value["foreground"], "windows": windows}


def exercise(title: str, duration: float = 3.0, interval: float = 0.05) -> dict:
    target = next((item for item in snapshot()["windows"] if item["title"] == title), None)
    if not target:
        return {"title": title, "found": False}
    hwnd = target["hwnd"]
    before = win32gui.GetForegroundWindow()
    if win32gui.IsIconic(hwnd):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    requested = bool(ctypes.windll.user32.SetForegroundWindow(hwnd))
    transitions = []
    previous = None
    deadline = time.monotonic() + duration
    while time.monotonic() < deadline:
        current = win32gui.GetForegroundWindow()
        if current != previous:
            transitions.append(
                {
                    "elapsed_ms": round((duration - max(0, deadline - time.monotonic())) * 1000, 1),
                    "window": window_info(current) if current else None,
                }
            )
            previous = current
        time.sleep(interval)
    return {
        "title": title,
        "found": True,
        "target": target,
        "foreground_before": int(before),
        "set_foreground_returned": requested,
        "transitions": transitions,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exercise", action="append", default=[])
    parser.add_argument("--duration", type=float, default=3.0)
    args = parser.parse_args(argv)
    result = {"snapshot": relevant(snapshot())}
    if args.exercise:
        result["exercises"] = [exercise(title, args.duration) for title in args.exercise]
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
