"""
core/gp_handler.py — Toàn bộ logic tương tác với GlobalProtect

Nhận diện trạng thái màn hình GP từ file log với offset tracking,
phát hiện sai mật khẩu ngay lập tức, tự phục hồi cửa sổ bị ẩn.
"""
import os
import re
import time
import socket
import tempfile
import uuid

import pyautogui

from adapters.base import OSAdapter
from vision.field_detector import detect_input_fields
from config import GP_PORTAL_URL, write_text_safely



# --- Các trạng thái có thể xảy ra ---
STATE_PORTAL = "PORTAL"
STATE_CREDENTIALS = "CREDENTIALS"
STATE_CONNECTED = "CONNECTED"
STATE_AUTH_FAILED = "AUTH_FAILED"
STATE_UNKNOWN = "UNKNOWN"


class GPHandler:
    """Xử lý toàn bộ luồng đăng nhập GlobalProtect."""

    def __init__(self, adapter: OSAdapter, log_fn=None):
        self.adapter = adapter
        self._log = log_fn or (lambda msg: None)
        self._log_offset: int = 0
        self._screenshot_tmp = os.path.join(
            tempfile.gettempdir(), f"gp_crop_{os.getpid()}_{uuid.uuid4().hex}.png"
        )
        self._debug_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "debug_gp_fields.png")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_already_connected(self, capam_ip: str, port: int = 443, timeout: int = 2) -> bool:
        """Kiểm tra nhanh xem VPN đã kết nối sẵn chưa."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(min(timeout, 0.5))
                s.connect((capam_ip, port))
            return True
        except Exception:
            return False

    def ensure_window_visible(self) -> dict | None:
        """Đảm bảo cửa sổ GP đang hiển thị. Tự khởi động lại nếu bị ẩn.
        Returns: rect dict hoặc None nếu vẫn không tìm được sau 2 lần thử.
        """
        rect = self.adapter.get_window_rect("GlobalProtect", exact=True)
        if not rect:
            self._log("Cửa sổ GlobalProtect không hiển thị, đang kích hoạt lại...")
            self.adapter.launch_gp_ui()
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                rect = self.adapter.get_window_rect("GlobalProtect", exact=True)
                if rect:
                    break
                time.sleep(0.5)
        if not rect:
            return None
        return rect

    def init_log_offset(self) -> None:
        """Ghi nhận kích thước file log hiện tại làm điểm mốc để chỉ đọc log mới."""
        try:
            log_path = self.adapter.get_gp_log_path()
            if os.path.exists(log_path):
                self._log_offset = os.path.getsize(log_path)
        except Exception:
            self._log_offset = 0

    def mark_log_before_submit(self) -> None:
        """Cập nhật điểm mốc log ngay trước khi nhấn nút đăng nhập."""
        self.init_log_offset()

    def read_state(self, read_all: bool = False) -> str:
        """Đọc trạng thái hiện tại của GP từ file log.

        Args:
            read_all: Nếu True, đọc toàn bộ cuối file log (30KB).
                      Nếu False, chỉ đọc phần log mới kể từ _log_offset.
        Returns:
            Một trong STATE_* constants.
        """
        log_path = self.adapter.get_gp_log_path()
        if not os.path.exists(log_path):
            return STATE_UNKNOWN
        try:
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                if read_all:
                    f.seek(0, 2)
                    size = f.tell()
                    f.seek(max(0, size - 30000))
                else:
                    current_size = os.path.getsize(log_path)
                    start = min(self._log_offset, current_size)
                    f.seek(start)
                content = f.read()

            matches = list(re.finditer(r"<response>.*?</response>", content, re.DOTALL))
            if not matches:
                return STATE_UNKNOWN
            last_msg = matches[-1].group(0)

            # Kiểm tra lỗi xác thực ngay lập tức (chỉ áp dụng khi đọc log mới)
            if not read_all:
                if "User authentication failed" in last_msg or "Authentication Failed" in last_msg:
                    return STATE_AUTH_FAILED


            if "<type>user_credential</type>" in last_msg:
                return STATE_CREDENTIALS
            elif "<type>status</type>" in last_msg:
                if "<state>Connected</state>" in last_msg:
                    return STATE_CONNECTED
                else:
                    return STATE_PORTAL
        except Exception as e:
            self._log(f"Lỗi đọc log GP: {e}")
        return STATE_UNKNOWN

    def detect_fields(self, rect: dict) -> list:
        """Chụp cửa sổ GP và phát hiện các ô nhập liệu bằng OpenCV."""
        current_rect = self.adapter.get_window_rect("GlobalProtect", exact=True)
        if not current_rect:
            return []
        rect = current_rect
        try:
            self.adapter.take_screenshot(rect, self._screenshot_tmp)
        except Exception:
            return []
        fields = detect_input_fields(
            self._screenshot_tmp,
            profile="gp",
            debug_output_path=None,
        )
        try:
            os.remove(self._screenshot_tmp)
        except Exception:
            pass
        return fields

    def enter_portal_url(self, rect: dict, fields: list) -> bool:
        """Điền URL portal vào ô nhập và nhấn Connect."""
        for attempt in range(3):
            if attempt > 0:
                self._log(f"[Portal] Thử lại nhập portal lần {attempt + 1}...")

            if not self.adapter.focus_window("GlobalProtect", exact=True):
                self._log("[Portal] Không thể đưa GlobalProtect lên foreground.")
                time.sleep(0.5)
                continue
            current_rect = self.adapter.get_window_rect("GlobalProtect", exact=True)
            if not current_rect or any(
                rect.get(key) != current_rect.get(key) for key in ("id", "w", "h")
            ):
                self._log("[Portal] Cửa sổ GlobalProtect đã thay đổi; bỏ tọa độ cũ.")
                return False
            rect = current_rect
            if fields:
                x0, y0, w0, h0 = fields[0]
                click_x = rect["x"] + x0 + w0 // 2
                click_y = rect["y"] + y0 + h0 // 2
                self._log(f"[Portal] Dùng tọa độ OpenCV: ({click_x}, {click_y})")
            else:
                click_x = rect["x"] + int(rect["w"] * 0.5)
                click_y = rect["y"] + int(rect["h"] * 0.78)
                self._log(f"[Portal] Dùng tọa độ tỷ lệ %: ({click_x}, {click_y})")

            pyautogui.click(click_x, click_y)
            time.sleep(0.1)
            pyautogui.hotkey("ctrl", "a")
            time.sleep(0.1)
            pyautogui.press("backspace")
            time.sleep(0.1)
            write_text_safely(GP_PORTAL_URL)
            time.sleep(0.1)
            pyautogui.press("enter")
            self._log(f"Đã nhập portal '{GP_PORTAL_URL}', chờ chuyển trang đăng nhập...")
            return True
            
        self._log("[Portal] Thất bại sau 3 lần thử nhập portal.")
        return False

    def enter_credentials(self, rect: dict, fields: list, username: str, password: str) -> bool:
        """Điền tài khoản và mật khẩu vào màn hình đăng nhập GP."""
        for attempt in range(3):
            if attempt > 0:
                self._log(f"[Credentials] Thử lại đăng nhập GP lần {attempt + 1}...")

            if not self.adapter.focus_window("GlobalProtect", exact=True):
                self._log("[Credentials] Không thể đưa GlobalProtect lên foreground.")
                time.sleep(0.5)
                continue
            current_rect = self.adapter.get_window_rect("GlobalProtect", exact=True)
            if not current_rect or any(
                rect.get(key) != current_rect.get(key) for key in ("id", "w", "h")
            ):
                self._log("[Credentials] Cửa sổ GlobalProtect đã thay đổi; bỏ tọa độ cũ.")
                return False
            rect = current_rect
            if len(fields) >= 2:
                x0, y0, w0, h0 = fields[0]
                click_x0 = rect["x"] + x0 + w0 // 2
                click_y0 = rect["y"] + y0 + h0 // 2
                x1, y1, w1, h1 = fields[1]
                click_x1 = rect["x"] + x1 + w1 // 2
                click_y1 = rect["y"] + y1 + h1 // 2
                self._log(f"[Credentials] OpenCV — User: ({click_x0}, {click_y0}), Pass: ({click_x1}, {click_y1})")
            else:
                click_x0 = rect["x"] + int(rect["w"] * 0.5)
                click_y0 = rect["y"] + int(rect["h"] * 0.59)
                click_x1 = rect["x"] + int(rect["w"] * 0.5)
                click_y1 = rect["y"] + int(rect["h"] * 0.69)
                self._log(f"[Credentials] Tỷ lệ % — User: ({click_x0}, {click_y0}), Pass: ({click_x1}, {click_y1})")

            # Nhập username
            pyautogui.click(click_x0, click_y0)
            time.sleep(0.1)
            pyautogui.hotkey("ctrl", "a")
            time.sleep(0.1)
            pyautogui.press("backspace")
            time.sleep(0.1)
            write_text_safely(username)
            time.sleep(0.1)

            # Nhập password
            pyautogui.click(click_x1, click_y1)
            time.sleep(0.1)
            pyautogui.hotkey("ctrl", "a")
            time.sleep(0.1)
            pyautogui.press("backspace")
            time.sleep(0.1)
            write_text_safely(password)
            time.sleep(0.1)
            return True
            
        self._log("[Credentials] Thất bại sau 3 lần thử nhập thông tin đăng nhập GP.")
        return False

    def submit_credentials(self, rect: dict) -> bool:
        """Gửi thông tin đăng nhập bằng cách nhấn Enter trên cửa sổ GP."""
        for attempt in range(3):
            if attempt > 0:
                self._log(f"[Credentials] Thử lại gửi Enter lần {attempt + 1}...")
            if not self.adapter.focus_window("GlobalProtect", exact=True):
                self._log("[Credentials] Không thể đưa GlobalProtect lên foreground để gửi Enter.")
                time.sleep(0.5)
                continue
            pyautogui.press("enter")
            return True
        return False


    def wait_connected_or_fail(self, capam_ip: str, port: int = 443, timeout_sec: int = 25) -> str:
        """Chờ VPN kết nối hoặc phát hiện lỗi xác thực.

        Polling mỗi 0.5 giây, tối đa timeout_sec giây.
        Returns:
            'CONNECTED' | 'AUTH_FAILED' | 'TIMEOUT'
        """
        deadline = time.monotonic() + timeout_sec
        while time.monotonic() < deadline:
            poll_started = time.monotonic()
            # Kiểm tra kết nối mạng
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.2)
                    s.connect((capam_ip, port))
                return "CONNECTED"
            except Exception:
                pass
            # Kiểm tra lỗi xác thực trong log mới
            state = self.read_state(read_all=False)
            if state == STATE_AUTH_FAILED:
                return "AUTH_FAILED"
            remaining = min(deadline, poll_started + 0.5) - time.monotonic()
            if remaining > 0:
                time.sleep(remaining)
        return "TIMEOUT"
