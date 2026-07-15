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
