"""
config.py — Cấu hình toàn cục, hằng số và helper functions
"""
import os
import sys
import platform

# --- Hằng số ---
CAPAM_IP_DEFAULT = "10.64.213.188"
GP_PORTAL_URL = "vpn.gdt.gov.vn"

# --- DPI Awareness (Windows) ---
if platform.system() == "Windows":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor DPI aware
    except Exception:
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def get_resource_path(relative_path: str) -> str:
    """Lấy đường dẫn tuyệt đối tĩnh (hỗ trợ cả môi trường PyInstaller)."""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


def write_text_safely(text: str) -> None:
    """Sao chép text vào clipboard và dán (Ctrl+V) để tránh lỗi bộ gõ tiếng Việt (Telex/VNI)
    biến các ký tự lặp thành chữ có dấu (ví dụ: 'Aa' -> 'Â').
    Sau khi dán, clipboard sẽ được phục hồi lại dữ liệu cũ để tránh ảnh hưởng đến người dùng.
    """
    if not text:
        return
    import pyperclip
    import pyautogui
    import time

    old_clipboard = ""
    try:
        old_clipboard = pyperclip.paste()
    except Exception:
        pass

    try:
        pyperclip.copy(text)
        time.sleep(0.05)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.05)
    except Exception:
        # Fallback trong trường hợp clipboard bị lỗi/chặn
        pyautogui.write(text, interval=0.03)
    finally:
        # Khôi phục lại clipboard cũ của người dùng
        try:
            pyperclip.copy(old_clipboard if old_clipboard else "")
        except Exception:
            try:
                pyperclip.copy("")
            except Exception:
                pass

