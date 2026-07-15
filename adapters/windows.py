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
        # Attach thread input để vượt qua Windows focus-stealing prevention
        foreground_thread = user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), None)
        target_thread = user32.GetWindowThreadProcessId(hwnd, None)
        if foreground_thread != target_thread:
            user32.AttachThreadInput(foreground_thread, target_thread, True)
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.SetForegroundWindow(hwnd)
        if foreground_thread != target_thread:
            user32.AttachThreadInput(foreground_thread, target_thread, False)
        return True
    except Exception:
        return False


def _get_clean_env() -> dict:
    import sys
    env = os.environ.copy()
    
    # 1. Xóa các biến môi trường liên quan đến Java hệ thống để buộc launcher dùng JRE đi kèm
    for var in ["JAVA_HOME", "CLASSPATH", "JAVA_EXE", "JVM_PATH"]:
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


class WindowsAdapter(OSAdapter):

    def focus_window(self, title_keyword: str, exact: bool = False) -> bool:
        try:
            import pygetwindow as gw
            windows = gw.getWindowsWithTitle(title_keyword)
            if not windows:
                return False
            # Ưu tiên khớp chính xác để tránh nhầm với tab trình duyệt
            if exact or title_keyword == "GlobalProtect":
                exact_wins = [w for w in windows if w.title == title_keyword]
                win = exact_wins[0] if exact_wins else windows[0]
            else:
                win = windows[0]
            # Thử Win32 API force focus trước
            try:
                import ctypes
                hwnd = ctypes.windll.user32.FindWindowW(None, win.title)
                if hwnd:
                    _force_foreground(hwnd)
                    time.sleep(0.3)
                    return True
            except Exception:
                pass
            # Fallback: pygetwindow activate
            if win.isMinimized:
                win.restore()
            win.activate()
            time.sleep(0.5)
            return True
        except Exception:
            return False

    def get_window_rect(self, title_keyword: str, exact: bool = False) -> dict | None:
        try:
            import pygetwindow as gw
            windows = gw.getWindowsWithTitle(title_keyword)
            if not windows:
                return None
            if exact or title_keyword == "GlobalProtect":
                exact_wins = [w for w in windows if w.title == title_keyword]
                if not exact_wins:
                    return None
                win = exact_wins[0]
            else:
                win = windows[0]
            return {
                "x": win.left,
                "y": win.top,
                "w": win.width,
                "h": win.height,
                "id": "win_id",
            }
        except Exception:
            return None

    def take_screenshot(self, rect: dict, path: str) -> None:
        from PIL import ImageGrab
        bbox = (rect["x"], rect["y"], rect["x"] + rect["w"], rect["y"] + rect["h"])
        ImageGrab.grab(bbox=bbox).save(path)

    def take_full_screenshot(self, path: str) -> None:
        from PIL import ImageGrab
        ImageGrab.grab().save(path)

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
                subprocess.Popen([exe], env=env, cwd=os.path.dirname(exe))
                return True
            except Exception:
                pass
        # Thử trực tiếp từ PATH
        try:
            subprocess.Popen(["CAPAMClient.exe"], env=env)
            return True
        except Exception:
            return False

    def launch_gp_ui(self) -> bool:
        env = _get_clean_env()
        for gp_path in GP_EXE_PATHS:
            if os.path.exists(gp_path):
                try:
                    subprocess.Popen([gp_path], env=env, cwd=os.path.dirname(gp_path))
                    return True
                except Exception:
                    pass
        try:
            subprocess.Popen(["PanGPA.exe"], env=env)
            return True
        except Exception:
            return False

    def get_gp_log_path(self) -> str:
        return os.path.expanduser(
            r"~\AppData\Local\Palo Alto Networks\GlobalProtect\PanGPA.log"
        )
