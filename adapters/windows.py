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
    """Dùng Win32 API để force cửa sổ lên foreground, vượt qua UIPI."""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        # 1. Khôi phục nếu cửa sổ đang bị thu nhỏ (minimized)
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        else:
            user32.ShowWindow(hwnd, 5)  # SW_SHOW

        # 2. Đưa cửa sổ lên trên cùng của Z-order bằng SetWindowPos
        # HWND_TOPMOST = -1, HWND_NOTOPMOST = -2
        # SWP_NOSIZE = 0x0001, SWP_NOMOVE = 0x0002, SWP_SHOWWINDOW = 0x0040
        user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0040)
        user32.SetWindowPos(hwnd, -2, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0040)

        # 3. Attach thread input của tiến trình Python hiện tại vào foreground thread và target thread
        current_thread = kernel32.GetCurrentThreadId()
        foreground_thread = user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), None)
        target_thread = user32.GetWindowThreadProcessId(hwnd, None)

        attached_fore = False
        attached_target = False

        if foreground_thread and current_thread != foreground_thread:
            attached_fore = bool(user32.AttachThreadInput(current_thread, foreground_thread, True))
        if target_thread and current_thread != target_thread:
            attached_target = bool(user32.AttachThreadInput(current_thread, target_thread, True))

        try:
            # 4. Set foreground và Bring to top
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
            user32.SetFocus(hwnd)

            # Chờ cửa sổ thực sự lên foreground
            deadline = time.monotonic() + 0.5
            while time.monotonic() < deadline:
                if user32.GetForegroundWindow() == hwnd:
                    return True
                time.sleep(0.02)
            return user32.GetForegroundWindow() == hwnd
        finally:
            # Detach threads
            if attached_target:
                user32.AttachThreadInput(current_thread, target_thread, False)
            if attached_fore:
                user32.AttachThreadInput(current_thread, foreground_thread, False)
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
    def _find_window(title_keyword: str, exact: bool = False):
        import ctypes
        import pygetwindow as gw

        windows = gw.getWindowsWithTitle(title_keyword)
        if exact or title_keyword == "GlobalProtect":
            windows = [window for window in windows if window.title == title_keyword]
        windows = [
            window for window in windows
            if not window.isMinimized and window.width > 0 and window.height > 0
        ]
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
            for _ in range(3):
                if hwnd and _force_foreground(hwnd):
                    return True
                time.sleep(0.05)
            # Fallback: pygetwindow activate
            if win.isMinimized:
                win.restore()
            win.activate()
            deadline = time.monotonic() + 0.3
            while time.monotonic() < deadline:
                if not hwnd or ctypes.windll.user32.GetForegroundWindow() == hwnd:
                    return True
                time.sleep(0.02)
            return not hwnd or ctypes.windll.user32.GetForegroundWindow() == hwnd
        except Exception:
            return False

    def focus_rect(self, rect: dict) -> bool:
        hwnd = rect.get("id")
        if not hwnd:
            return False
        try:
            import ctypes
            if ctypes.windll.user32.GetForegroundWindow() == hwnd:
                return True
            for _ in range(3):
                if _force_foreground(hwnd):
                    return True
                time.sleep(0.05)
            return ctypes.windll.user32.GetForegroundWindow() == hwnd
        except Exception:
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
