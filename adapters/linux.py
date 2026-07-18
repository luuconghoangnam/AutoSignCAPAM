"""
adapters/linux.py — Linux implementation của OSAdapter
"""
import os
import subprocess
import time

from adapters.base import OSAdapter


class LinuxAdapter(OSAdapter):

    def get_capam_main_rect(self) -> dict | None:
        return self.get_window_rect("Symantec Privileged Access Manager", exact=True)

    def get_capam_dialog_rect(self) -> dict | None:
        return self.get_window_rect("Symantec Privileged Access Manager", exact=True)

    def get_window_rect_for_hwnd(self, hwnd) -> dict | None:
        try:
            out = subprocess.check_output(["wmctrl", "-l", "-G"]).decode("utf-8")
            for line in out.splitlines():
                parts = line.split()
                if len(parts) >= 6 and parts[0].lower() == str(hwnd).lower():
                    return {
                        "x": int(parts[2]),
                        "y": int(parts[3]),
                        "w": int(parts[4]),
                        "h": int(parts[5]),
                        "id": parts[0],
                    }
        except Exception:
            pass
        return None

    def focus_window(self, title_keyword: str, exact: bool = False) -> bool:
        try:
            if exact:
                subprocess.run(["wmctrl", "-F", "-a", title_keyword], check=False)
            else:
                subprocess.run(["wmctrl", "-a", title_keyword], check=False)
            time.sleep(0.5)
            return True
        except Exception:
            return False

    def focus_rect(self, rect: dict) -> bool:
        window_id = rect.get("id")
        if not window_id:
            return False
        try:
            subprocess.run(["wmctrl", "-i", "-a", str(window_id)], check=False)
            time.sleep(0.1)
            return self.is_foreground(rect)
        except Exception:
            return False

    def wait_focus_rect(self, rect: dict, timeout: float = 5.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.focus_rect(rect):
                return True
            time.sleep(0.2)
        return False

    def suppress_browser_foreground(self) -> bool:
        return False

    def is_foreground(self, rect: dict) -> bool:
        try:
            active = subprocess.check_output(["xdotool", "getactivewindow"]).decode().strip()
            return int(active) == int(str(rect.get("id")), 16)
        except Exception:
            return False

    def get_window_rect(self, title_keyword: str, exact: bool = False) -> dict | None:
        try:
            out = subprocess.check_output(["wmctrl", "-l", "-G"]).decode("utf-8")
            for line in out.splitlines():
                title = " ".join(line.split()[7:])
                matches = title == title_keyword if exact else title_keyword.lower() in title.lower()
                if matches:
                    parts = line.split()
                    if len(parts) >= 6:
                        return {
                            "x": int(parts[2]),
                            "y": int(parts[3]),
                            "w": int(parts[4]),
                            "h": int(parts[5]),
                            "id": parts[0],
                        }
        except Exception:
            pass
        return None

    def take_screenshot(self, rect: dict, path: str) -> None:
        display = os.environ.get("DISPLAY", ":0")
        subprocess.run(
            ["maim", "-g", f"{rect['w']}x{rect['h']}+{rect['x']}+{rect['y']}", path],
            env={"DISPLAY": display},
            check=True,
        )

    def capture_window(self, rect: dict):
        return None

    def take_full_screenshot(self, path: str) -> None:
        display = os.environ.get("DISPLAY", ":0")
        subprocess.run(["maim", path], env={"DISPLAY": display}, check=True)

    def is_capam_running(self) -> bool:
        return subprocess.run(
            ["pgrep", "-f", "CAPAMClient"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode == 0

    def kill_capam(self) -> bool:
        return subprocess.run(["pkill", "-f", "CAPAMClient"], check=False).returncode in (0, 1)

    def launch_capam(self) -> bool:
        try:
            subprocess.Popen(
                [os.path.expanduser("~/CAPAMClient/CAPAMClient")],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except Exception:
            return False

    def launch_gp_ui(self) -> bool:
        try:
            import dbus
            bus = dbus.SessionBus()
            watcher_obj = bus.get_object("org.kde.StatusNotifierWatcher", "/StatusNotifierWatcher")
            watcher = dbus.Interface(watcher_obj, "org.freedesktop.DBus.Properties")
            items = watcher.Get("org.kde.StatusNotifierWatcher", "RegisteredStatusNotifierItems")
            for item in items:
                parts = item.split("/", 1)
                bus_name = parts[0]
                path = "/" + parts[1] if len(parts) > 1 else "/StatusNotifierItem"
                item_obj = bus.get_object(bus_name, path)
                props = dbus.Interface(item_obj, "org.freedesktop.DBus.Properties")
                if props.Get("org.kde.StatusNotifierItem", "Id") == "PanGPUI":
                    notifier = dbus.Interface(item_obj, "org.kde.StatusNotifierItem")
                    notifier.Activate(0, 0)
                    return True
        except Exception:
            pass
        subprocess.run(["globalprotect", "launch-ui"], check=False)
        return True

    def get_gp_log_path(self) -> str:
        return os.path.expanduser("~/.GlobalProtect/PanGPUI.log")
