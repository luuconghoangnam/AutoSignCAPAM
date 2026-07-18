"""Observe automation and Windows app state without clicking or reading secrets.

Example:
    python -m tools.monitor_flow --duration 120 --output artifacts/diagnostics/flow.jsonl
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import time
import uuid
from pathlib import Path

from diagnostics.timeline import TimelineWriter
from tools.collect_windows import list_windows


WATCH_TITLES = (
    "CAPAM AutoSign",
    "GlobalProtect",
    "Symantec Privileged Access Manager",
    "Windows Security",
    "Remote Desktop",
    "RDP-211.200",
    "Terminal-211.12",
)


def _window_summary(window: dict) -> dict:
    topmost = None
    try:
        import win32gui

        topmost = bool(win32gui.GetWindowLong(window.get("hwnd"), -20) & 0x00000008)
    except Exception:
        pass
    return {
        "title": window.get("title"),
        "hwnd": window.get("hwnd"),
        "pid": window.get("pid"),
        "process_name": Path(window.get("process_path") or "").name or None,
        "x": window.get("x"),
        "y": window.get("y"),
        "width": window.get("width"),
        "height": window.get("height"),
        "minimized": window.get("minimized"),
        "topmost": topmost,
    }


def _watched_windows() -> list[dict]:
    watched = []
    for window in list_windows():
        process_name = Path(window.get("process_path") or "").name.lower()
        title_match = any(title.lower() in window["title"].lower() for title in WATCH_TITLES)
        if not title_match:
            continue
        if "remote desktop" in window["title"].lower() and process_name != "mstsc.exe":
            continue
        watched.append(_window_summary(window))
    return watched


def _processes() -> list[dict]:
    try:
        import win32process

        watched = {"pangpa.exe", "pangps.exe", "capamclient.exe", "mstsc.exe", "python.exe", "autosigncapam.exe"}
        result = []
        for pid in win32process.EnumProcesses():
            if not pid:
                continue
            handle = None
            try:
                import win32api
                import win32con

                handle = win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
                path = win32process.GetModuleFileNameEx(handle, 0)
                name = Path(path).name.lower()
                if name in watched:
                    result.append({"pid": pid, "name": name})
            except Exception:
                continue
            finally:
                if handle:
                    handle.Close()
        return sorted(result, key=lambda item: (item["name"], item["pid"]))
    except Exception as exc:
        return [{"available": False, "error": type(exc).__name__}]


def _tool_state(hwnd: int) -> dict:
    try:
        import uiautomation as auto

        root = auto.ControlFromHandle(hwnd)
        stack = [root]
        buttons = {}
        while stack:
            control = stack.pop()
            if control.ControlTypeName == "ButtonControl" and control.Name in (
                "TIẾN HÀNH ĐĂNG NHẬP", "HỦY"
            ):
                buttons[control.Name] = bool(control.IsEnabled)
            stack.extend(control.GetChildren())
        return {
            "available": True,
            "run_enabled": buttons.get("TIẾN HÀNH ĐĂNG NHẬP"),
            "cancel_enabled": buttons.get("HỦY"),
            "worker_active": buttons.get("HỦY") is True,
        }
    except Exception as exc:
        return {"available": False, "error": type(exc).__name__}


def _foreground_state(hwnd: int | None) -> dict | None:
    if not hwnd:
        return None
    try:
        import win32gui
        import win32process

        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        process_name = None
        for process in _processes():
            if process.get("pid") == pid:
                process_name = process.get("name")
                break
        return {
            "hwnd": hwnd,
            "pid": pid,
            "process_name": process_name,
            "title": win32gui.GetWindowText(hwnd),
        }
    except Exception as exc:
        return {"hwnd": hwnd, "error": type(exc).__name__}


def _capture_metrics(window: dict, profile: str) -> dict:
    from adapters.windows import WindowsAdapter
    from capture.frame import FrameSnapshot
    from vision.field_detector import detect_input_fields

    adapter = WindowsAdapter()
    window_rect = adapter.get_window_rect_for_hwnd(window["hwnd"])
    rect = adapter.get_capture_rect_for_hwnd(window["hwnd"])
    image = adapter.capture_window(window_rect) if window_rect else None
    if image is None:
        return {"capture": "unavailable", "hwnd": window["hwnd"]}
    snapshot = FrameSnapshot.from_image(image, rect)
    result = {
        "capture": "ok",
        "hwnd": window["hwnd"],
        "image_size": [int(image.shape[1]), int(image.shape[0])],
        "capture_rect": {
            key: rect.get(key) for key in ("x", "y", "w", "h", "id")
        },
        "fingerprint": snapshot.fingerprint,
        "stddev": round(snapshot.standard_deviation, 3),
        "blank": snapshot.is_blank,
    }
    # Vision diagnostics use temporary file only; no image artifact is retained.
    temp = Path(os.environ.get("TEMP", ".")) / f"autosign-monitor-{uuid.uuid4().hex}.png"
    try:
        import cv2

        cv2.imwrite(str(temp), image)
        fields = detect_input_fields(str(temp), profile=profile)
        result["profile"] = profile
        result["field_count"] = len(fields)
        result["field_boxes"] = [list(field) for field in fields]
    finally:
        temp.unlink(missing_ok=True)
    return result


def _semantic_summary(hwnd: int) -> dict:
    from tools.probe_jab import probe_jab
    from tools.probe_uia import probe_uia

    jab = probe_jab(hwnd)
    uia = probe_uia(hwnd, max_depth=5)
    names = {name.rstrip(":").strip().lower() for name in _collect_values(jab.get("controls", []), "name")}
    return {
        "jab": {
            "available": jab.get("available", False),
            "reason": jab.get("reason"),
            "bridge_name": Path(jab.get("bridge") or "").name or None,
            "control_count": _count_nodes(jab.get("controls", [])),
            "roles": sorted(_collect_values(jab.get("controls", []), "role")),
            "has_address_control": "address" in names,
            "has_connect_mode_control": "connect mode" in names,
            "has_connect_control": "connect" in names,
            "has_username_control": "username" in names,
            "has_password_control": "password" in names,
            "has_login_control": "login" in names,
        },
        "uia": {
            "available": uia.get("available", False),
            "reason": uia.get("reason"),
            "control_count": _count_nodes([uia.get("tree", {})] if uia.get("tree") else []),
        },
    }


def _count_nodes(nodes: list[dict]) -> int:
    return sum(1 + _count_nodes(node.get("children", [])) for node in nodes)


def _collect_values(nodes: list[dict], key: str) -> set[str]:
    values = set()
    for node in nodes:
        value = node.get(key)
        if value:
            values.add(str(value))
        values.update(_collect_values(node.get("children", []), key))
    return values


def _network_state(host: str, port: int = 443) -> dict:
    started = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return {"reachable": True, "latency_ms": round((time.monotonic() - started) * 1000, 2)}
    except OSError as exc:
        return {"reachable": False, "error": type(exc).__name__}


def monitor(duration: float, interval: float, output: str, capam_ip: str) -> Path:
    session_id = os.environ.get("AUTOMATION_SESSION_ID", uuid.uuid4().hex)
    writer = TimelineWriter(output, source="monitor", session_id=session_id, redact_otp=False)
    started = time.monotonic()
    previous = None
    semantic_at = 0.0
    semantic = None
    while time.monotonic() - started < duration:
        windows = _watched_windows()
        foreground = None
        try:
            import ctypes

            foreground = ctypes.windll.user32.GetForegroundWindow()
        except Exception:
            pass
        snapshot = {
            "windows": windows,
            "processes": _processes(),
            "foreground_hwnd": foreground,
            "foreground": _foreground_state(foreground),
            "network": _network_state(capam_ip),
        }
        tool = next((window for window in windows if window["title"] == "CAPAM AutoSign"), None)
        if tool:
            snapshot["tool"] = _tool_state(tool["hwnd"])
        app_observations = {}
        gp = next((window for window in windows if window["title"] == "GlobalProtect"), None)
        if gp:
            app_observations[str(gp["hwnd"])] = {
                "app": "globalprotect",
                "vision": _capture_metrics(gp, "gp"),
            }
        capam = next((window for window in windows if "privileged access manager" in window["title"].lower()), None)
        if capam:
            profile = "capam" if capam["title"] == "Symantec Privileged Access Manager" else "device-list"
            app_observations[str(capam["hwnd"])] = {
                "app": profile,
                "vision": _capture_metrics(capam, "capam"),
            }
            if time.monotonic() >= semantic_at:
                semantic = _semantic_summary(capam["hwnd"])
                semantic_at = time.monotonic() + 2.0
            app_observations[str(capam["hwnd"])]["semantic"] = semantic
        if app_observations:
            snapshot["app_observations"] = app_observations
        digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
        if digest != previous:
            writer.emit("observation", digest=digest, **snapshot)
            previous = digest
        time.sleep(max(0.05, interval))
    writer.emit("monitor_finished", elapsed_s=round(time.monotonic() - started, 3))
    return Path(output)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration", type=float, default=120)
    parser.add_argument("--interval", type=float, default=0.5)
    parser.add_argument("--output", default="artifacts/diagnostics/flow-timeline.jsonl")
    parser.add_argument("--capam-ip", default="10.64.213.188")
    args = parser.parse_args(argv)
    print(monitor(args.duration, args.interval, args.output, args.capam_ip))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
