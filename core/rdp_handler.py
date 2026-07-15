"""
core/rdp_handler.py — Click nút RDP và điền thông tin vào bảng Windows Security
"""
import os
import time

import cv2
import pyautogui

from adapters.base import OSAdapter
from vision.template_matcher import find_device_rdp_button
from vision.field_detector import detect_input_fields
from config import write_text_safely


WIN_SEC_TITLE = "Symantec Privileged Access Manager"


class RDPHandler:
    """Xử lý luồng click RDP và điền thông tin Windows Security."""

    def __init__(self, adapter: OSAdapter, log_fn=None):
        self.adapter = adapter
        self._log = log_fn or (lambda msg: None)
        self._screenshot_tmp = os.path.join(os.environ.get("TEMP", "/tmp"), "capam_full_scr.tmp.png")
        self._debug_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "debug_capam_fields.png")

    def wait_for_device_list(self, capam_ip: str, max_wait: int = 30) -> dict | None:
        """Chờ cửa sổ danh sách thiết bị CAPAM xuất hiện.
        Returns: rect dict hoặc None nếu timeout.
        """
        target_title = f"Symantec Privileged Access Manager Client - {capam_ip}"
        for i in range(max_wait * 2):
            rect = self.adapter.get_window_rect(target_title)
            if rect:
                self._log(f"Đã phát hiện danh sách thiết bị sau {i * 0.5:.1f} giây.")
                return rect
            time.sleep(0.5)
        self._log("Quá thời gian chờ danh sách thiết bị CAPAM.")
        return None

    def click_rdp(self, device_choice: str, max_attempts: int = 30) -> bool:
        """Chụp màn hình, tìm và click nút RDP cho thiết bị được chọn.
        Thử tối đa max_attempts lần với interval 1 giây.
        Returns: True nếu click thành công.
        """
        for attempt in range(max_attempts):
            self._log(f"Đang tìm nút RDP... (Lần {attempt + 1}/{max_attempts})")
            # Chụp toàn màn hình
            try:
                self.adapter.take_full_screenshot(self._screenshot_tmp)
            except Exception as e:
                self._log(f"Lỗi chụp màn hình: {e}")
                pyautogui.screenshot(self._screenshot_tmp)

            scene = cv2.imread(self._screenshot_tmp)
            try:
                os.remove(self._screenshot_tmp)
            except Exception:
                pass

            result = find_device_rdp_button(scene, device_choice, log_fn=self._log)
            if result:
                click_x, click_y = result
                self._log(f"Đang click nút RDP tại ({click_x}, {click_y})...")
                pyautogui.click(click_x, click_y)
                return True
            time.sleep(1)
        return False

    def fill_windows_security(self, username: str, password: str) -> bool:
        """Chờ và điền thông tin đăng nhập vào bảng Windows Security.
        Returns: True nếu hoàn tất.
        """
        self._log("Đang chờ bảng Windows Security xuất hiện...")
        rect = None
        screenshot_tmp = os.path.join(os.environ.get("TEMP", "/tmp"), "win_sec_crop.tmp.png")

        for attempt in range(20):
            rect = self.adapter.get_window_rect(WIN_SEC_TITLE, exact=True)
            if rect:
                self._log(f"Đã phát hiện bảng xác thực RDP CAPAM sau {attempt} giây.")
                break
            time.sleep(1)

        if not rect:
            self._log("Không tìm thấy bảng xác thực RDP CAPAM trong 20 giây.")
            return False

        time.sleep(0.5)
        self.adapter.focus_window(WIN_SEC_TITLE, exact=True)
        time.sleep(0.5)

        # Phát hiện ô nhập liệu trong bảng xác thực RDP CAPAM
        fields = []
        for attempt in range(10):
            try:
                self.adapter.focus_window(WIN_SEC_TITLE, exact=True)
                self.adapter.take_screenshot(rect, screenshot_tmp)
            except Exception:
                pass
            
            fields = detect_input_fields(screenshot_tmp, profile="capam")
            try:
                os.remove(screenshot_tmp)
            except Exception:
                pass
            if len(fields) >= 1:
                break
            self._log(f"Đang chờ ô nhập liệu của bảng xác thực RDP CAPAM... (Lần {attempt+1}/10)")
            time.sleep(0.5)
            
        self._log(f"Bảng xác thực RDP CAPAM: Phát hiện thấy {len(fields)} ô nhập liệu.")

        if len(fields) < 1:
            self._log("Không tìm thấy ô nhập liệu nào trong bảng xác thực RDP CAPAM.")
            return False

        x0, y0, w0, h0 = fields[0]

        # Username
        pyautogui.click(rect["x"] + x0 + w0 // 2, rect["y"] + y0 + h0 // 2)
        time.sleep(0.15)
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.1)
        write_text_safely(username)
        self._log(f"Đã nhập Username Windows Security: {username}")

        # Password
        time.sleep(0.2)
        pyautogui.press("tab")
        time.sleep(0.15)
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.1)
        write_text_safely(password)
        self._log("Đã nhập Password Windows Security.")

        time.sleep(0.3)
        pyautogui.press("enter")
        self._log("Đã nhấn Login Windows Security — kết nối RDP đang thiết lập!")
        return True
