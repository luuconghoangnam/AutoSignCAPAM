"""Probe Java Access Bridge tree without persisting control values."""
from __future__ import annotations

import os


def probe_jab(hwnd: int) -> dict:
    if os.name != "nt":
        return {"available": False, "reason": "not-windows"}
    jab = None
    try:
        from adapters.windows import WindowsAdapter
        from automation.java_access_bridge import CAPAMJAB

        capam_exe = WindowsAdapter().find_capam_exe()
        if not capam_exe:
            return {"available": False, "reason": "capam-executable-not-found"}
        bridge = CAPAMJAB.find_bridge(capam_exe)
        if not bridge:
            return {"available": False, "reason": "bridge-not-found", "capam_exe": capam_exe}
        jab = CAPAMJAB(bridge)
        jab.attach(hwnd=hwnd)
        return {
            "available": True,
            "hwnd": hwnd,
            "capam_exe": capam_exe,
            "bridge": bridge,
            "controls": jab.snapshot_controls(),
        }
    except Exception as exc:
        return {"available": False, "reason": type(exc).__name__, "message": str(exc)}
    finally:
        if jab:
            jab.close()
