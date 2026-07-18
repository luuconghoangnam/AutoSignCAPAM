"""
core/gp_handler.py — Toàn bộ logic tương tác với GlobalProtect

Nhận diện trạng thái màn hình GP từ file log với offset tracking,
phát hiện sai mật khẩu ngay lập tức, tự phục hồi cửa sổ bị ẩn.
"""
import os
import re
import time
import socket
import subprocess
import tempfile
import uuid

import pyautogui

from adapters.base import OSAdapter
from capture.window_capture import FrameCapture
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

    def __init__(self, adapter: OSAdapter, log_fn=None, cancel_fn=None):
        self.adapter = adapter
        self._log = log_fn or (lambda msg: None)
        self._cancelled = cancel_fn or (lambda: False)
        self._log_offset: int = 0
        self._capture = FrameCapture(adapter)
        self._screenshot_tmp = os.path.join(
            tempfile.gettempdir(), f"gp_crop_{os.getpid()}_{uuid.uuid4().hex}.png"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_already_connected(self, capam_ip: str, port: int = 443, timeout: int = 2) -> bool:
        """Check GP state first; CAPAM port 443 is only a fallback probe."""
        if self.read_state(read_all=True) == STATE_CONNECTED:
            return True
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(min(timeout, 0.5))
                s.connect((capam_ip, port))
            return True
        except Exception:
            return self._ping_host(capam_ip)

    @staticmethod
    def _ping_host(host: str, timeout_ms: int = 400) -> bool:
        """ICMP fallback; VPN may route host while CAPAM TCP 443 stays closed."""
        try:
            command = (
                ["ping", "-n", "1", "-w", str(timeout_ms), host]
                if os.name == "nt"
                else ["ping", "-c", "1", "-W", "1", host]
            )
            result = subprocess.run(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=max(1.0, timeout_ms / 1000 + 0.5),
                check=False,
                creationflags=0x08000000 if os.name == "nt" else 0,
            )
            return result.returncode == 0
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
                if self._cancelled():
                    return None
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

            matches = list(re.finditer(r"<response(?:\s[^>]*)?>.*?</response>", content, re.DOTALL))
            if not matches:
                return STATE_UNKNOWN

            # Ignore trailing keep-alive responses such as <disabled>no</disabled>.
            for match in reversed(matches):
                message = match.group(0)
                if not read_all and (
                    "User authentication failed" in message
                    or "Authentication Failed" in message
                ):
                    return STATE_AUTH_FAILED
                if "<type>user_credential</type>" in message:
                    return STATE_CREDENTIALS
                if "<type>status</type>" in message:
                    if (
                        "<state>Connected</state>" in message
                        or "<status>Connected</status>" in message
                    ):
                        return STATE_CONNECTED
                    return STATE_PORTAL
        except Exception as e:
            self._log(f"Lỗi đọc log GP: {e}")
        return STATE_UNKNOWN

    def detect_fields(self, rect: dict) -> list:
        """Chụp cửa sổ GP và phát hiện các ô nhập liệu bằng OpenCV."""
        snapshot = self._capture.capture(rect)
        if not snapshot or snapshot.is_blank:
            return []
        try:
            import cv2

            cv2.imwrite(self._screenshot_tmp, snapshot.image)
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

    @staticmethod
    def classify_fields(fields: list, width: int, height: int) -> str:
        """Classify calibrated GP geometry; reject count-only false positives."""
        if width <= 0 or height <= 0:
            return STATE_UNKNOWN
        if len(fields) == 1:
            x, y, w, h = fields[0]
            if w / width >= 0.5 and h / height >= 0.04 and y / height >= 0.65:
                return STATE_PORTAL
            return STATE_UNKNOWN
        if len(fields) == 2:
            first, second = sorted(fields, key=lambda item: item[1])
            x0, y0, w0, h0 = first
            x1, y1, w1, h1 = second
            aligned = abs(x0 - x1) / width <= 0.05 and abs(w0 - w1) / width <= 0.08
            ordered = 0.04 <= (y1 - y0) / height <= 0.25
            practical = min(w0, w1) / width >= 0.5 and min(h0, h1) / height >= 0.04
            if aligned and ordered and practical:
                return STATE_CREDENTIALS
        return STATE_UNKNOWN

    def enter_portal_url(self, rect: dict, fields: list) -> bool:
        """Điền URL portal vào ô nhập và nhấn Connect."""
        if not self.adapter.focus_rect(rect):
            self._log("[Portal] Không thể đưa đúng cửa sổ GlobalProtect lên foreground.")
            return False
        current_rect = self.adapter.get_window_rect_for_hwnd(rect.get("id"))
        if not current_rect or any(
            rect.get(key) != current_rect.get(key) for key in ("id", "w", "h")
        ):
            self._log("[Portal] Cửa sổ GlobalProtect đã thay đổi; bỏ tọa độ cũ.")
            return False
        rect = current_rect
        get_capture_rect = getattr(self.adapter, "get_capture_rect_for_hwnd", None)
        image_rect = get_capture_rect(rect.get("id")) if get_capture_rect else None
        image_rect = image_rect or rect
        if fields:
            x0, y0, w0, h0 = fields[0]
            click_x = image_rect["x"] + x0 + w0 // 2
            click_y = image_rect["y"] + y0 + h0 // 2
            self._log(f"[Portal] Dùng tọa độ OpenCV: ({click_x}, {click_y})")
        else:
            click_x = rect["x"] + int(rect["w"] * 0.5)
            click_y = rect["y"] + int(rect["h"] * 0.78)
            self._log(f"[Portal] Dùng tọa độ tỷ lệ %: ({click_x}, {click_y})")

        pyautogui.click(click_x, click_y)
        time.sleep(0.1)
        if not self.adapter.is_foreground(rect):
            self._log("[Portal] Foreground đổi sau click; dừng nhập portal.")
            return False
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.1)
        pyautogui.press("backspace")
        time.sleep(0.1)
        if not write_text_safely(GP_PORTAL_URL, lambda: self.adapter.is_foreground(rect)):
            return False
        time.sleep(0.1)
        if not self.adapter.is_foreground(rect):
            self._log("[Portal] Foreground đổi trong lúc nhập; không nhấn Enter.")
            return False
        pyautogui.press("enter")
        self._log(f"Đã nhập portal '{GP_PORTAL_URL}', chờ chuyển trang đăng nhập...")
        return True

    def enter_credentials(self, rect: dict, fields: list, username: str, password: str) -> bool:
        """Điền tài khoản và mật khẩu vào màn hình đăng nhập GP."""
        if not self.adapter.focus_rect(rect):
            self._log("[Credentials] Không thể đưa đúng cửa sổ GlobalProtect lên foreground.")
            return False
        current_rect = self.adapter.get_window_rect_for_hwnd(rect.get("id"))
        if not current_rect or any(
            rect.get(key) != current_rect.get(key) for key in ("id", "w", "h")
        ):
            self._log("[Credentials] Cửa sổ GlobalProtect đã thay đổi; bỏ tọa độ cũ.")
            return False
        rect = current_rect
        get_capture_rect = getattr(self.adapter, "get_capture_rect_for_hwnd", None)
        image_rect = get_capture_rect(rect.get("id")) if get_capture_rect else None
        image_rect = image_rect or rect
        if len(fields) >= 2:
            x0, y0, w0, h0 = fields[0]
            click_x0 = image_rect["x"] + x0 + w0 // 2
            click_y0 = image_rect["y"] + y0 + h0 // 2
            x1, y1, w1, h1 = fields[1]
            click_x1 = image_rect["x"] + x1 + w1 // 2
            click_y1 = image_rect["y"] + y1 + h1 // 2
        else:
            click_x0 = rect["x"] + int(rect["w"] * 0.5)
            click_y0 = rect["y"] + int(rect["h"] * 0.59)
            click_x1 = rect["x"] + int(rect["w"] * 0.5)
            click_y1 = rect["y"] + int(rect["h"] * 0.69)

        pyautogui.click(click_x0, click_y0)
        time.sleep(0.1)
        if not self.adapter.is_foreground(rect):
            return False
        pyautogui.hotkey("ctrl", "a")
        pyautogui.press("backspace")
        if not write_text_safely(username, lambda: self.adapter.is_foreground(rect)):
            return False
        pyautogui.click(click_x1, click_y1)
        time.sleep(0.1)
        if not self.adapter.is_foreground(rect):
            return False
        pyautogui.hotkey("ctrl", "a")
        pyautogui.press("backspace")
        if not write_text_safely(password, lambda: self.adapter.is_foreground(rect)):
            return False
        return self.adapter.is_foreground(rect)

    def submit_credentials(self, rect: dict) -> bool:
        """Gửi thông tin đăng nhập bằng cách nhấn Enter trên cửa sổ GP."""
        if not self.adapter.is_foreground(rect):
            self._log("[Credentials] Foreground đã đổi; không gửi Enter.")
            return False
        pyautogui.press("enter")
        return True


    def wait_connected_or_fail(
        self,
        capam_ip: str,
        port: int = 443,
        timeout_sec: int = 25,
        keep_foreground_rect: dict | None = None,
        restore_if_capam_foreground: bool = False,
        suppress_browser_foreground: bool = False,
    ) -> str:
        """Chờ VPN kết nối hoặc phát hiện lỗi xác thực.

        Polling mỗi 0.5 giây, tối đa timeout_sec giây.
        Returns:
            'CONNECTED' | 'AUTH_FAILED' | 'TIMEOUT'
        """
        deadline = time.monotonic() + timeout_sec
        next_ping_at = time.monotonic()
        while time.monotonic() < deadline:
            if self._cancelled():
                return "TIMEOUT"
            poll_started = time.monotonic()
            if keep_foreground_rect and restore_if_capam_foreground:
                capam_rect = self.adapter.get_capam_main_rect()
                if capam_rect and self.adapter.is_foreground(capam_rect):
                    self.adapter.focus_rect(keep_foreground_rect)
            # GP log is authoritative. CAPAM may intentionally block TCP 443.
            state = self.read_state(read_all=False)
            if state == STATE_CONNECTED:
                if suppress_browser_foreground:
                    # Browser callback is normally activated immediately after this log event.
                    time.sleep(0.15)
                    self.adapter.suppress_browser_foreground()
                return "CONNECTED"
            if state == STATE_AUTH_FAILED:
                return "AUTH_FAILED"

            # TCP probe remains useful when GP log is delayed or unavailable.
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.2)
                    s.connect((capam_ip, port))
                return "CONNECTED"
            except Exception:
                pass
            if poll_started >= next_ping_at:
                if self._ping_host(capam_ip):
                    return "CONNECTED"
                next_ping_at = poll_started + 1.0
            remaining = min(deadline, poll_started + 0.25) - time.monotonic()
            if remaining > 0:
                time.sleep(remaining)
        return "TIMEOUT"
