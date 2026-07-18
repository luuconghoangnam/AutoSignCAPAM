"""
adapters/windows.py — Windows implementation của OSAdapter
Tính năng nâng cấp:
  - Smart path discovery: Quét nhiều đường dẫn + registry + PATH
  - SetForegroundWindow Win32 API để force focus (vượt qua UIPI blocking)
  - Exact window title matching để tránh nhầm với tab trình duyệt
"""
import os
import subprocess
import threading
import time
from contextlib import contextmanager
from types import SimpleNamespace

from adapters.base import OSAdapter
from adapters.window_identity import WindowBounds, WindowIdentity, WindowRef, identity_matches
from adapters.windows_discovery import discover


def _force_foreground(hwnd) -> bool:
    """Activate target without temporary topmost or global Z-order churn."""
    try:
        import ctypes
        user32 = ctypes.windll.user32

        if not user32.IsWindow(hwnd) or not user32.IsWindowVisible(hwnd):
            return False
        if user32.GetForegroundWindow() == hwnd:
            return True

        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE

        user32.SetForegroundWindow(hwnd)

        # Chờ cửa sổ thực sự lên foreground
        deadline = time.monotonic() + 0.3
        while time.monotonic() < deadline:
            if user32.GetForegroundWindow() == hwnd:
                return True
            time.sleep(0.02)
        return user32.GetForegroundWindow() == hwnd
    except Exception:
        return False


def _switch_to_window(hwnd) -> bool:
    """Task-switch exact HWND without making it topmost."""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        if not user32.IsWindow(hwnd):
            return False
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.SwitchToThisWindow(hwnd, True)
        deadline = time.monotonic() + 0.4
        while time.monotonic() < deadline:
            if user32.GetForegroundWindow() == hwnd:
                return True
            time.sleep(0.02)
        return False
    except Exception:
        return False


_DLL_DIRECTORY_LOCK = threading.Lock()


def _get_clean_env() -> dict:
    import sys
    env = os.environ.copy()
    
    # 1. Xóa các biến môi trường liên quan đến Java hệ thống để buộc launcher dùng JRE đi kèm
    for var in [
        "JAVA_HOME", "CLASSPATH", "JAVA_EXE", "JVM_PATH",
        "RC_JAVA_ACCESS_BRIDGE_DLL", "ROBOT_ARTIFACTS",
    ]:
        env.pop(var, None)

    # Tiến trình ngoài không được kế thừa metadata bootloader one-file.
    for var in list(env):
        if var.startswith("_PYI_") or var == "PYINSTALLER_RESET_ENVIRONMENT":
            env.pop(var, None)
        
    # 2. Loại bỏ thư mục tạm _MEIPASS của PyInstaller và các đường dẫn JDK/JRE khỏi PATH
    path_val = env.get("PATH", "")
    if path_val:
        path_list = path_val.split(os.pathsep)
        clean_path_list = []
        for p in path_list:
            if not p or not os.path.isabs(p):
                continue
            p_norm = os.path.normpath(p)
            p_lower = p_norm.lower()
            
            # Loại bỏ _MEIPASS
            if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
                if p_lower == os.path.normpath(sys._MEIPASS).lower():
                    continue
            
            # Loại bỏ bất kỳ đường dẫn nào chứa jdk, jre, java, oracle để ngắt kết nối tới Java hệ thống
            if "jdk" in p_lower or "jre" in p_lower or "java" in p_lower or "oracle" in p_lower:
                continue
                
            clean_path_list.append(p)
        env["PATH"] = os.pathsep.join(clean_path_list)
        
    return env


@contextmanager
def _external_process_context():
    """Tách DLL search path của tiến trình ngoài khỏi thư mục PyInstaller _MEI."""
    import ctypes
    import sys

    kernel32 = ctypes.windll.kernel32
    frozen_dir = getattr(sys, "_MEIPASS", None)
    with _DLL_DIRECTORY_LOCK:
        kernel32.SetDllDirectoryW(None)
        try:
            yield
        finally:
            if frozen_dir:
                kernel32.SetDllDirectoryW(frozen_dir)


def _launch_external(command: list[str], env: dict, cwd: str | None = None) -> None:
    with _external_process_context():
        subprocess.Popen(
            command,
            env=env,
            cwd=cwd,
            close_fds=True,
            creationflags=0x00000200,  # CREATE_NEW_PROCESS_GROUP
        )


class WindowsAdapter(OSAdapter):

    def __init__(self):
        self.last_discovery = {}
        self._suppressed_windows = []
        self._diagnostic_fn = None
        self._browser_callback_suppression = True
        self._gp_callback_window = None

    def _diag(self, event: str, **data) -> None:
        if self._diagnostic_fn:
            self._diagnostic_fn(event, **data)

    @staticmethod
    def is_gp_browser_callback(process_name: str, title: str) -> bool:
        browsers = {
            "chrome.exe", "msedge.exe", "firefox.exe", "brave.exe",
            "opera.exe", "coccoc.exe", "whale.exe", "iexplore.exe",
        }
        return (
            process_name.lower() in browsers
            and "globalprotect" in title.lower()
        )

    @staticmethod
    def _window_ref(hwnd: int) -> WindowRef | None:
        try:
            import ctypes
            import win32gui
            import win32process

            if not win32gui.IsWindow(hwnd):
                return None
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            process_path = None
            process_created = None
            process = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
            if process:
                try:
                    buffer = ctypes.create_unicode_buffer(1024)
                    size = ctypes.c_ulong(len(buffer))
                    if ctypes.windll.kernel32.QueryFullProcessImageNameW(
                        process, 0, buffer, ctypes.byref(size)
                    ):
                        process_path = buffer.value
                    created = (ctypes.c_ulong * 2)()
                    exited = (ctypes.c_ulong * 2)()
                    kernel = (ctypes.c_ulong * 2)()
                    user = (ctypes.c_ulong * 2)()
                    if ctypes.windll.kernel32.GetProcessTimes(
                        process,
                        ctypes.byref(created), ctypes.byref(exited),
                        ctypes.byref(kernel), ctypes.byref(user),
                    ):
                        process_created = (created[1] << 32) | created[0]
                finally:
                    ctypes.windll.kernel32.CloseHandle(process)
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            client = (ctypes.c_long * 4)()
            origin = (ctypes.c_long * 2)()
            if not ctypes.windll.user32.GetClientRect(hwnd, client):
                return None
            if not ctypes.windll.user32.ClientToScreen(hwnd, origin):
                return None
            identity = WindowIdentity(
                hwnd=int(hwnd),
                pid=pid,
                process_name=os.path.basename(process_path or ""),
                process_path=process_path,
                process_created=process_created,
                class_name=win32gui.GetClassName(hwnd),
                title=win32gui.GetWindowText(hwnd),
                owner_hwnd=int(win32gui.GetWindow(hwnd, 4) or 0),
            )
            return WindowRef(
                identity=identity,
                outer=WindowBounds(left, top, right - left, bottom - top),
                client=WindowBounds(
                    origin[0], origin[1], client[2] - client[0], client[3] - client[1]
                ),
            )
        except Exception:
            return None

    def validate_window(self, expected: dict) -> dict | None:
        hwnd = expected.get("id") if expected else None
        ref = self._window_ref(hwnd) if hwnd else None
        current = ref.as_dict() if ref else None
        if not current or not identity_matches(expected, current):
            self._diag(
                "window_validation_failed",
                hwnd=hwnd,
                expected_pid=expected.get("pid") if expected else None,
                actual_pid=current.get("pid") if current else None,
            )
            return None
        return current

    @staticmethod
    def _foreground_process_name() -> str | None:
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            pid = ctypes.c_ulong()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            process = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid.value)
            if not process:
                return None
            try:
                buffer = ctypes.create_unicode_buffer(1024)
                size = ctypes.c_ulong(len(buffer))
                if ctypes.windll.kernel32.QueryFullProcessImageNameW(
                    process, 0, buffer, ctypes.byref(size)
                ):
                    return os.path.basename(buffer.value).lower()
            finally:
                ctypes.windll.kernel32.CloseHandle(process)
        except Exception:
            pass
        return None

    def suppress_browser_foreground(self) -> bool:
        if not self._browser_callback_suppression:
            return False
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            ref = self._window_ref(hwnd) if hwnd else None
            if not ref:
                return False
            identity = ref.identity
            callback = self.is_gp_browser_callback(identity.process_name, identity.title)
            tracked = self._gp_callback_window
            same_tracked_window = bool(
                tracked
                and identity.hwnd == tracked.get("id")
                and identity.pid == tracked.get("pid")
                and identity.process_created == tracked.get("process_created")
            )
            if not callback and not same_tracked_window:
                return False
            expected = ref.as_dict()
            if callback:
                self._gp_callback_window = expected.copy()
            if self.validate_window(expected) and ctypes.windll.user32.GetForegroundWindow() == hwnd:
                import pyautogui

                # Close only the correlated GP callback tab. If browser reused an
                # existing window, Ctrl+W reveals the previous user tab unchanged.
                pyautogui.hotkey("ctrl", "w")
                self._diag(
                    "gp_browser_callback_closed",
                    hwnd=hwnd,
                    pid=identity.pid,
                    process_name=identity.process_name,
                    title=identity.title,
                )
                self._gp_callback_window = None
                return True
        except Exception:
            pass
        return False

    def set_browser_callback_suppression(self, enabled: bool) -> None:
        self._browser_callback_suppression = bool(enabled)
        if not enabled:
            self._gp_callback_window = None

    def restore_suppressed_windows(self) -> None:
        # Legacy minimized callbacks from earlier runs are restored; current
        # policy closes only exact GP callback tabs and creates no restore debt.
        import ctypes
        for expected in self._suppressed_windows:
            current = self.validate_window(expected)
            if current and ctypes.windll.user32.IsIconic(current["id"]):
                ctypes.windll.user32.ShowWindow(current["id"], 9)  # SW_RESTORE
        self._suppressed_windows.clear()

    @staticmethod
    def _window_candidates(title_keyword: str, exact: bool = False):
        import win32gui

        windows = []

        def visit(hwnd, _lparam):
            if not win32gui.IsWindowVisible(hwnd):
                return
            title = win32gui.GetWindowText(hwnd)
            matches = title == title_keyword if exact else title_keyword.lower() in title.lower()
            if not matches:
                return
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            width, height = right - left, bottom - top
            if width > 0 and height > 0:
                ref = WindowsAdapter._window_ref(hwnd)
                if not ref:
                    return
                windows.append(
                    SimpleNamespace(
                        title=title,
                        left=left,
                        top=top,
                        width=width,
                        height=height,
                        _hWnd=hwnd,
                        ref=ref,
                    )
                )

        win32gui.EnumWindows(visit, None)
        return windows

    @classmethod
    def _find_window(cls, title_keyword: str, exact: bool = False):
        import ctypes

        windows = cls._window_candidates(
            title_keyword,
            exact=exact or title_keyword == "GlobalProtect",
        )

        if not windows:
            return None

        foreground = ctypes.windll.user32.GetForegroundWindow()
        foreground_window = next(
            (window for window in windows if getattr(window, "_hWnd", None) == foreground),
            None,
        )
        if foreground_window:
            return foreground_window

        # Popup xác thực CAPAM có cùng exact title với cửa sổ đăng nhập cũ,
        # nhưng là dialog nhỏ hơn. Ưu tiên dialog nhỏ để tránh chụp nhầm.
        if exact and title_keyword == "Symantec Privileged Access Manager":
            return min(windows, key=lambda window: window.width * window.height)
        return windows[0]

    def focus_window(self, title_keyword: str, exact: bool = False) -> bool:
        try:
            import ctypes
            win = self._find_window(title_keyword, exact)
            if not win:
                return False
            hwnd = getattr(win, "_hWnd", None)
            if hwnd and ctypes.windll.user32.GetForegroundWindow() == hwnd:
                return True
            return bool(hwnd and _force_foreground(hwnd))
        except Exception:
            return False

    def focus_rect(self, rect: dict) -> bool:
        started = time.monotonic()
        current = self.validate_window(rect)
        if not current:
            self._diag("focus_result", allowed=False, reason="identity-invalid")
            return False
        hwnd = current["id"]
        try:
            import ctypes
            if ctypes.windll.user32.IsWindow(hwnd) == 0:
                return False
            result = _force_foreground(hwnd)
            self._diag(
                "focus_result", allowed=result, hwnd=hwnd, pid=current.get("pid"),
                elapsed_ms=round((time.monotonic() - started) * 1000, 2),
            )
            return result
        except Exception:
            return False

    def wait_focus_rect(self, rect: dict, timeout: float = 5.0) -> bool:
        hwnd = rect.get("id")
        if not hwnd:
            return False
        deadline = time.monotonic() + timeout
        attempt = 0
        while time.monotonic() < deadline:
            current = self.validate_window(rect)
            if not current:
                return False
            if self.is_foreground(current):
                return True
            attempt += 1
            activated = _force_foreground(hwnd)
            if not activated and attempt >= 2:
                activated = _switch_to_window(hwnd)
            if activated and self.is_foreground(current):
                # Browser callbacks may steal focus immediately after activation.
                time.sleep(0.15)
                if self.is_foreground(current):
                    return True
            time.sleep(0.2)
        return False

    def is_foreground(self, rect: dict) -> bool:
        current = self.validate_window(rect)
        if not current:
            return False
        hwnd = current["id"]
        try:
            import ctypes
            return ctypes.windll.user32.GetForegroundWindow() == hwnd
        except Exception:
            return False


    def get_window_rect(self, title_keyword: str, exact: bool = False) -> dict | None:
        try:
            win = self._find_window(title_keyword, exact)
            if not win:
                return None
            result = win.ref.as_dict()
            expected_process = None
            if title_keyword == "GlobalProtect":
                expected_process = "PanGPA.exe"
            elif title_keyword.startswith("Symantec Privileged Access Manager"):
                expected_process = "CAPAMClient.exe"
            elif title_keyword in ("RDP-211.200", "Terminal-211.12"):
                expected_process = "CAPAMClient.exe"
            if expected_process and result["process_name"].lower() != expected_process.lower():
                self._diag(
                    "window_rejected", title=title_keyword,
                    expected_process=expected_process, actual_process=result["process_name"],
                )
                return None
            self._diag("window_discovered", query=title_keyword, exact=exact, window=result)
            return result
        except Exception:
            return None

    def get_capam_main_rect(self) -> dict | None:
        """Choose unowned exact-title CAPAM window; dialogs have an owner HWND."""
        try:
            import ctypes
            windows = self._window_candidates("Symantec Privileged Access Manager", exact=True)
            if not windows:
                return None
            unowned = [
                window for window in windows
                if not ctypes.windll.user32.GetWindow(getattr(window, "_hWnd", 0), 4)  # GW_OWNER
            ]
            if not unowned:
                return None
            unowned = [
                window for window in unowned
                if window.ref.identity.process_name.lower() == "capamclient.exe"
            ]
            if not unowned:
                return None
            window = max(unowned, key=lambda item: item.width * item.height)
            return window.ref.as_dict()
        except Exception:
            return None

    def get_capam_dialog_rect(self) -> dict | None:
        """Choose owned exact-title CAPAM authentication dialog."""
        try:
            import ctypes
            windows = self._window_candidates("Symantec Privileged Access Manager", exact=True)
            if not windows:
                return None
            if len(windows) == 1:
                window = windows[0]
                return None
            owned = [
                window for window in windows
                if ctypes.windll.user32.GetWindow(getattr(window, "_hWnd", 0), 4)  # GW_OWNER
                and window.ref.identity.process_name.lower() == "capamclient.exe"
            ]
            if not owned:
                return None
            window = min(owned, key=lambda item: item.width * item.height)
            return window.ref.as_dict()
        except Exception:
            return None

    def get_window_rect_for_hwnd(self, hwnd) -> dict | None:
        ref = self._window_ref(hwnd) if hwnd else None
        return ref.as_dict() if ref else None

    def get_capture_rect_for_hwnd(self, hwnd) -> dict | None:
        """Return physical screen bounds represented by HWND ImageGrab pixels."""
        if not hwnd:
            return None
        try:
            import ctypes

            user32 = ctypes.windll.user32
            if not user32.IsWindow(hwnd):
                return None
            client = (ctypes.c_long * 4)()
            origin = (ctypes.c_long * 2)()
            if not user32.GetClientRect(hwnd, client):
                return None
            if not user32.ClientToScreen(hwnd, origin):
                return None
            ref = self._window_ref(hwnd)
            return {**ref.client.as_dict(), "id": hwnd} if ref else None
        except Exception:
            return None

    def get_window_rects(self, title_keyword: str, exact: bool = False) -> list[dict]:
        results = []
        for window in self._window_candidates(title_keyword, exact=exact):
            item = window.ref.as_dict()
            expected_process = None
            if title_keyword == "GlobalProtect":
                expected_process = "PanGPA.exe"
            elif title_keyword.startswith("Symantec Privileged Access Manager"):
                expected_process = "CAPAMClient.exe"
            elif title_keyword in ("RDP-211.200", "Terminal-211.12"):
                expected_process = "CAPAMClient.exe"
            if not expected_process or item["process_name"].lower() == expected_process.lower():
                results.append(item)
        return results

    def kill_window_process(self, rect: dict) -> bool:
        current = self.validate_window(rect)
        if not current:
            return False
        hwnd = current["id"]
        try:
            import ctypes
            pid = ctypes.c_ulong()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if not pid.value:
                return False
            subprocess.run(
                ["taskkill", "/F", "/PID", str(pid.value)],
                check=False,
                creationflags=0x08000000,
            )
            return True
        except Exception:
            return False

    def take_screenshot(self, rect: dict, path: str) -> None:
        from PIL import Image, ImageGrab
        hwnd = rect.get("id")
        image = None
        if hwnd:
            try:
                # Chụp trực tiếp HWND, không phụ thuộc cửa sổ có đang foreground
                # hay bị cửa sổ khác che. Alt+Tab trước đây vô tình sửa đúng vấn
                # đề này bằng cách đưa CAPAM lên trên cùng.
                image = ImageGrab.grab(window=hwnd, include_layered_windows=True)
            except Exception:
                image = None
        if image is None:
            bbox = (rect["x"], rect["y"], rect["x"] + rect["w"], rect["y"] + rect["h"])
            image = ImageGrab.grab(bbox=bbox)
        if image.size != (rect["w"], rect["h"]):
            # PyInstaller/PyQt có thể khởi tạo DPI context trước config.py, làm
            # ImageGrab trả physical pixel còn pygetwindow trả logical pixel.
            image = image.resize((rect["w"], rect["h"]), Image.Resampling.LANCZOS)
        image.save(path)

    def capture_window(self, rect: dict):
        """Capture HWND directly into BGR memory without PNG disk round-trip."""
        from PIL import ImageGrab
        import numpy as np
        hwnd = rect.get("id")
        if not hwnd:
            return None
        try:
            image = ImageGrab.grab(window=hwnd, include_layered_windows=True).convert("RGB")
            return np.asarray(image)[:, :, ::-1].copy()
        except Exception:
            return None

    def take_full_screenshot(self, path: str) -> None:
        from PIL import ImageGrab
        ImageGrab.grab().save(path)

    def refresh_window(self, rect: dict) -> None:
        hwnd = rect.get("id")
        if not hwnd:
            return
        try:
            import ctypes
            # RDW_INVALIDATE | RDW_UPDATENOW | RDW_ALLCHILDREN
            ctypes.windll.user32.RedrawWindow(hwnd, None, None, 0x0181)
        except Exception:
            pass

    def is_capam_running(self) -> bool:
        try:
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq CAPAMClient.exe", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                check=False,
                creationflags=0x08000000,
            )
            return any(
                line.strip().lower().startswith('"capamclient.exe"')
                for line in result.stdout.splitlines()
            )
        except Exception:
            return bool(self.get_window_rects("Symantec Privileged Access Manager"))

    def kill_capam(self) -> bool:
        try:
            if not self.is_capam_running():
                return True
            return subprocess.run(
                ["taskkill", "/F", "/T", "/IM", "CAPAMClient.exe"],
                check=False,
                creationflags=0x08000000,
            ).returncode == 0
        except Exception:
            return False

    def find_capam_exe(self) -> str | None:
        """Resolve verified absolute CAPAM executable from supported sources."""
        result = discover("capam")
        self.last_discovery["capam"] = result
        self._diag(
            "executable_discovered", product="capam", found=bool(result),
            source=result.source if result else None,
            executable_name=result.executable.name if result else None,
            install_root_name=result.install_root.name if result else None,
        )
        return str(result.executable) if result else None

    def find_gp_exe(self) -> str | None:
        """Resolve absolute GlobalProtect UI executable from supported sources."""
        result = discover("gp")
        self.last_discovery["gp"] = result
        self._diag(
            "executable_discovered", product="globalprotect", found=bool(result),
            source=result.source if result else None,
            executable_name=result.executable.name if result else None,
            install_root_name=result.install_root.name if result else None,
        )
        return str(result.executable) if result else None

    def launch_capam(self) -> bool:
        exe = self.find_capam_exe()
        env = _get_clean_env()
        if exe:
            try:
                # Đặt cwd là thư mục chứa exe để Java tìm đúng các file cấu hình và DLL đi kèm của nó
                _launch_external([exe], env=env, cwd=os.path.dirname(exe))
                return True
            except Exception:
                pass
        return False

    def launch_gp_ui(self) -> bool:
        env = _get_clean_env()
        gp_path = self.find_gp_exe()
        if not gp_path:
            return False
        try:
            _launch_external([gp_path], env=env, cwd=os.path.dirname(gp_path))
            return True
        except Exception:
            return False

    def click_window_point(self, rect: dict, screen_x: int, screen_y: int) -> bool:
        current = self.validate_window(rect)
        if not current:
            return False
        try:
            import ctypes

            hwnd = current["id"]
            point = (ctypes.c_long * 2)(screen_x, screen_y)
            if not ctypes.windll.user32.ScreenToClient(hwnd, point):
                return False
            if not (0 <= point[0] < current["client_rect"]["w"]):
                return False
            if not (0 <= point[1] < current["client_rect"]["h"]):
                return False
            lparam = (point[1] & 0xFFFF) << 16 | (point[0] & 0xFFFF)
            user32 = ctypes.windll.user32
            user32.SendMessageW(hwnd, 0x0200, 0, lparam)  # WM_MOUSEMOVE
            user32.SendMessageW(hwnd, 0x0201, 0x0001, lparam)  # WM_LBUTTONDOWN
            user32.SendMessageW(hwnd, 0x0202, 0, lparam)  # WM_LBUTTONUP
            self._diag(
                "window_direct_click",
                hwnd=hwnd,
                screen_x=screen_x,
                screen_y=screen_y,
                client_x=point[0],
                client_y=point[1],
            )
            return True
        except Exception:
            return False

    def get_gp_log_path(self) -> str:
        return os.path.expanduser(
            r"~\AppData\Local\Palo Alto Networks\GlobalProtect\PanGPA.log"
        )

    def get_rdp_windows(self) -> dict[int, str]:
        """Return visible top-level HWNDs and titles owned by mstsc.exe."""
        try:
            import ctypes
            import win32gui

            kernel32 = ctypes.windll.kernel32
            result = {}

            def visit(hwnd, _):
                if not win32gui.IsWindowVisible(hwnd):
                    return
                _, pid = __import__("win32process").GetWindowThreadProcessId(hwnd)
                process = kernel32.OpenProcess(0x1000, False, pid)
                if not process:
                    return
                try:
                    buffer = ctypes.create_unicode_buffer(1024)
                    size = ctypes.c_ulong(len(buffer))
                    if kernel32.QueryFullProcessImageNameW(process, 0, buffer, ctypes.byref(size)):
                        if os.path.basename(buffer.value).lower() == "mstsc.exe":
                            result[int(hwnd)] = win32gui.GetWindowText(hwnd)
                finally:
                    kernel32.CloseHandle(process)

            win32gui.EnumWindows(visit, None)
            return result
        except Exception:
            return {}

    def window_belongs_to_process(self, hwnd: int, process_name: str) -> bool:
        if not hwnd:
            return False
        try:
            import ctypes

            pid = ctypes.c_ulong()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            process = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid.value)
            if not process:
                return False
            try:
                buffer = ctypes.create_unicode_buffer(1024)
                size = ctypes.c_ulong(len(buffer))
                if not ctypes.windll.kernel32.QueryFullProcessImageNameW(
                    process, 0, buffer, ctypes.byref(size)
                ):
                    return False
                return os.path.basename(buffer.value).lower() == process_name.lower()
            finally:
                ctypes.windll.kernel32.CloseHandle(process)
        except Exception:
            return False
