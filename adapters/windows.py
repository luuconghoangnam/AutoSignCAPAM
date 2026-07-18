"""
adapters/windows.py — Windows implementation của OSAdapter
Tính năng nâng cấp:
  - Smart path discovery: Quét nhiều đường dẫn + registry + PATH
  - SetForegroundWindow Win32 API để force focus (vượt qua UIPI blocking)
  - Exact window title matching để tránh nhầm với tab trình duyệt
"""
import os
import subprocess
import time
from contextlib import contextmanager
from types import SimpleNamespace

from adapters.base import OSAdapter


# --- Danh sách đường dẫn cài đặt thường gặp của CAPAM Client ---
CAPAM_CANDIDATE_PATHS = [
    r"C:\Program Files\Broadcom\CAPAM Client\CAPAMClient.exe",
    r"C:\Program Files (x86)\Broadcom\CAPAM Client\CAPAMClient.exe",
    r"C:\Program Files\CA\CAPAM Client\CAPAMClient.exe",
    r"C:\Program Files (x86)\CA\CAPAM Client\CAPAMClient.exe",
    os.path.expanduser(r"~\CA PAM Client\CAPAMClient.exe"),
    os.path.expanduser(r"~\CAPAM Client\CAPAMClient.exe"),
]

GP_EXE_PATHS = [
    r"C:\Program Files\Palo Alto Networks\GlobalProtect\PanGPA.exe",
    r"C:\Program Files (x86)\Palo Alto Networks\GlobalProtect\PanGPA.exe",
]


def _find_capam_in_registry() -> str | None:
    """Tìm đường dẫn CAPAM Client trong Windows Registry."""
    try:
        import winreg
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            for sub in (
                r"SOFTWARE\Broadcom\CAPAM Client",
                r"SOFTWARE\CA\CAPAM Client",
                r"SOFTWARE\WOW6432Node\Broadcom\CAPAM Client",
            ):
                try:
                    with winreg.OpenKey(hive, sub) as key:
                        install_dir, _ = winreg.QueryValueEx(key, "InstallPath")
                        candidate = os.path.join(install_dir, "CAPAMClient.exe")
                        if os.path.exists(candidate):
                            return candidate
                except (FileNotFoundError, OSError):
                    continue
    except ImportError:
        pass
    return None


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

        # Put exact target at top of normal Z-order, never TOPMOST.
        # SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE | SWP_SHOWWINDOW
        user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010 | 0x0040)
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


def _get_clean_env() -> dict:
    import sys
    env = os.environ.copy()
    
    # 1. Xóa các biến môi trường liên quan đến Java hệ thống để buộc launcher dùng JRE đi kèm
    for var in ["JAVA_HOME", "CLASSPATH", "JAVA_EXE", "JVM_PATH"]:
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
        browsers = {
            "chrome.exe", "msedge.exe", "firefox.exe", "brave.exe",
            "opera.exe", "coccoc.exe", "whale.exe", "iexplore.exe"
        }
        if self._foreground_process_name() not in browsers:
            return False
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE
                return True
        except Exception:
            pass
        return False

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
                windows.append(
                    SimpleNamespace(
                        title=title,
                        left=left,
                        top=top,
                        width=width,
                        height=height,
                        _hWnd=hwnd,
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
        hwnd = rect.get("id")
        if not hwnd:
            return False
        try:
            import ctypes
            if ctypes.windll.user32.IsWindow(hwnd) == 0:
                return False
            return _force_foreground(hwnd)
        except Exception:
            return False

    def wait_focus_rect(self, rect: dict, timeout: float = 5.0) -> bool:
        hwnd = rect.get("id")
        if not hwnd:
            return False
        deadline = time.monotonic() + timeout
        attempt = 0
        while time.monotonic() < deadline:
            current = self.get_window_rect_for_hwnd(hwnd)
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
        hwnd = rect.get("id")
        if not hwnd:
            return False
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
            return {
                "x": win.left,
                "y": win.top,
                "w": win.width,
                "h": win.height,
                "id": getattr(win, "_hWnd", None),
            }
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
            window = max(unowned, key=lambda item: item.width * item.height)
            return {
                "x": window.left,
                "y": window.top,
                "w": window.width,
                "h": window.height,
                "id": getattr(window, "_hWnd", None),
            }
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
                return {
                    "x": window.left,
                    "y": window.top,
                    "w": window.width,
                    "h": window.height,
                    "id": getattr(window, "_hWnd", None),
                }
            owned = [
                window for window in windows
                if ctypes.windll.user32.GetWindow(getattr(window, "_hWnd", 0), 4)  # GW_OWNER
            ]
            if not owned:
                return None
            window = min(owned, key=lambda item: item.width * item.height)
            return {
                "x": window.left,
                "y": window.top,
                "w": window.width,
                "h": window.height,
                "id": getattr(window, "_hWnd", None),
            }
        except Exception:
            return None

    def get_window_rect_for_hwnd(self, hwnd) -> dict | None:
        if not hwnd:
            return None
        try:
            import ctypes
            rect = (ctypes.c_long * 4)()
            if not ctypes.windll.user32.IsWindow(hwnd):
                return None
            if not ctypes.windll.user32.GetWindowRect(hwnd, rect):
                return None
            return {
                "x": rect[0],
                "y": rect[1],
                "w": rect[2] - rect[0],
                "h": rect[3] - rect[1],
                "id": hwnd,
            }
        except Exception:
            return None

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
            return {
                "x": origin[0],
                "y": origin[1],
                "w": client[2] - client[0],
                "h": client[3] - client[1],
                "id": hwnd,
            }
        except Exception:
            return None

    def kill_window_process(self, rect: dict) -> bool:
        hwnd = rect.get("id")
        if not hwnd:
            return False
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

    def kill_capam(self) -> None:
        creationflags = 0x08000000  # CREATE_NO_WINDOW
        subprocess.run(
            ["taskkill", "/F", "/IM", "CAPAMClient.exe"],
            check=False,
            creationflags=creationflags,
        )

    def find_capam_exe(self) -> str | None:
        """Tìm đường dẫn thực thi CAPAMClient.exe theo thứ tự ưu tiên."""
        # 1. Kiểm tra các đường dẫn cài đặt thông thường
        for path in CAPAM_CANDIDATE_PATHS:
            if os.path.exists(path):
                return path
        # 2. Tìm trong registry
        registry_path = _find_capam_in_registry()
        if registry_path:
            return registry_path
        # 3. Fallback: thử chạy từ PATH
        return None

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
        # Thử trực tiếp từ PATH
        try:
            _launch_external(["CAPAMClient.exe"], env=env)
            return True
        except Exception:
            return False

    def launch_gp_ui(self) -> bool:
        env = _get_clean_env()
        for gp_path in GP_EXE_PATHS:
            if os.path.exists(gp_path):
                try:
                    _launch_external([gp_path], env=env, cwd=os.path.dirname(gp_path))
                    return True
                except Exception:
                    pass
        try:
            _launch_external(["PanGPA.exe"], env=env)
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
