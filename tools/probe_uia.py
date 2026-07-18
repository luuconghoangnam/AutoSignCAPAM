"""Optional UI Automation tree probe; never reads control values."""
from __future__ import annotations

import os


def _serialize(control, depth: int, max_depth: int, budget: list[int]) -> dict:
    budget[0] -= 1
    rect = control.BoundingRectangle
    item = {
        "control_type": str(control.ControlTypeName),
        "name": str(control.Name or ""),
        "automation_id": str(control.AutomationId or ""),
        "class_name": str(control.ClassName or ""),
        "help_text": str(control.HelpText or ""),
        "enabled": bool(control.IsEnabled),
        "offscreen": bool(control.IsOffscreen),
        "rect": {
            "x": int(rect.left),
            "y": int(rect.top),
            "width": int(rect.width()),
            "height": int(rect.height()),
        },
        "children": [],
    }
    if depth >= max_depth or budget[0] <= 0:
        return item
    for child in control.GetChildren():
        if budget[0] <= 0:
            break
        item["children"].append(_serialize(child, depth + 1, max_depth, budget))
    return item


def probe_uia(hwnd: int, max_depth: int = 8) -> dict:
    if os.name != "nt":
        return {"available": False, "reason": "not-windows"}
    try:
        import uiautomation as auto

        control = auto.ControlFromHandle(hwnd)
        if not control or not control.Exists(1):
            return {"available": False, "reason": "control-not-found"}
        return {
            "available": True,
            "hwnd": hwnd,
            "tree": _serialize(control, 0, max_depth, [500]),
        }
    except ImportError:
        return {"available": False, "reason": "install-tools-requirements"}
    except Exception as exc:
        return {"available": False, "reason": type(exc).__name__, "message": str(exc)}
