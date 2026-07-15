"""
core/capam_handler.py — Xử lý luồng khởi động và đăng nhập CAPAM Client
"""
import os
import time

import pyautogui

from adapters.base import OSAdapter
from vision.field_detector import detect_input_fields
from config import write_text_safely


CAPAM_WINDOW_TITLE = "Symantec Privileged Access Manager"


class CAPAMHandler:
    """Xử lý khởi động CAPAM Client và đăng nhập tài khoản."""

    def __init__(self, adapter: OSAdapter, capam_ip: str, log_fn=None):
        self.adapter = adapter
        self.capam_ip = capam_ip
        self._log = log_fn or (lambda msg: None)
        self._screenshot_tmp = os.path.join(os.environ.get("TEMP", "/tmp"), "capam_crop.tmp.png")
        self._debug_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "debug_capam_fields.png")

    def launch_and_wait(self, max_wait: int = 20) -> bool:
        """Khởi động CAPAM Client và chờ cửa sổ xuất hiện.
        Returns: True nếu tìm thấy cửa sổ trong thời gian chờ.
        """
        self._log("Đang khởi động CAPAM Client...")
        self.adapter.launch_capam()
        for i in range(max_wait):
            time.sleep(1)
            rect = self.adapter.get_window_rect(CAPAM_WINDOW_TITLE)
            if rect:
                self._log(f"Đã phát hiện cửa sổ CAPAM Client sau {i + 1} giây.")
                return True
            self._log(f"Đang chờ CAPAM khởi động... ({i + 1}/{max_wait}s)")
        self._log("Quá thời gian chờ CAPAM Client xuất hiện.")
        return False

    def detect_login_fields(self, rect: dict) -> list:
        """Phát hiện ô nhập liệu trên màn hình đăng nhập CAPAM."""
        try:
            self.adapter.take_screenshot(rect, self._screenshot_tmp)
        except Exception:
            return []
        fields = detect_input_fields(
            self._screenshot_tmp,
            profile="capam",
            debug_output_path=self._debug_path,
        )
        try:
            os.remove(self._screenshot_tmp)
        except Exception:
            pass
        return fields

    def wait_for_login_screen(self, max_wait: int = 15) -> tuple[dict | None, list]:
        """Chờ cho đến khi màn hình đăng nhập CAPAM có đủ ô nhập liệu.
        Returns: (rect, fields) hoặc (None, []) nếu timeout.
        """
        for attempt in range(max_wait):
            rect = self.adapter.get_window_rect(CAPAM_WINDOW_TITLE)
            if rect:
                fields = self.detect_login_fields(rect)
                if len(fields) >= 2:
                    return rect, fields
            self._log(f"Chờ màn hình đăng nhập CAPAM... ({attempt + 1}/{max_wait})")
            time.sleep(1)
        return None, []

    def enter_credentials(self, rect: dict, fields: list, username: str, password: str) -> bool:
        """Điền tài khoản/mật khẩu vào màn hình đăng nhập CAPAM và nhấn Connect.
        Returns: True nếu hoàn tất điền thông tin.
        """
        if len(fields) < 2:
            self._log("Không đủ ô nhập liệu để điền thông tin CAPAM.")
            return False

        x0, y0, w0, h0 = fields[0]
        x1, y1, w1, h1 = fields[1]

        click_x0 = rect["x"] + x0 + w0 // 2
        click_y0 = rect["y"] + y0 + h0 // 2
        click_x1 = rect["x"] + x1 + w1 // 2
        click_y1 = rect["y"] + y1 + h1 // 2

        # Username
        pyautogui.click(click_x0, click_y0)
        time.sleep(0.1)
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.1)
        pyautogui.press("backspace")
        time.sleep(0.1)
        write_text_safely(username)
        self._log(f"Đã nhập tài khoản CAPAM: {username}")

        # Password
        pyautogui.click(click_x1, click_y1)
        time.sleep(0.1)
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.1)
        pyautogui.press("backspace")
        time.sleep(0.1)
        write_text_safely(password)
        self._log("Đã nhập mật khẩu CAPAM.")

        time.sleep(0.3)
        pyautogui.press("enter")
        self._log("Đã gửi thông tin đăng nhập CAPAM.")
        return True
