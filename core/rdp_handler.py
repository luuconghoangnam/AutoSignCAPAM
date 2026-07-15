"""
core/rdp_handler.py — Click nút RDP và điền thông tin vào bảng Windows Security
"""
import os
import tempfile
import time
import uuid

import cv2
import pyautogui

from adapters.base import OSAdapter
from vision.template_matcher import find_device_rdp_button
from vision.field_detector import detect_input_fields
from config import write_text_safely


WIN_SEC_TITLE = "Symantec Privileged Access Manager"
WIN_SEC_TITLES = (WIN_SEC_TITLE, "Windows Security")
_POLL_INTERVAL = 0.5
_MIN_FIELD_WIDTH_RATIO = 0.25


class RDPHandler:
    """Xử lý luồng click RDP và điền thông tin Windows Security."""

    def __init__(self, adapter: OSAdapter, log_fn=None):
        self.adapter = adapter
        self._log = log_fn or (lambda msg: None)
        run_id = f"{os.getpid()}_{uuid.uuid4().hex}"
        self._screenshot_tmp = os.path.join(tempfile.gettempdir(), f"capam_window_{run_id}.png")
        self._win_sec_tmp = os.path.join(tempfile.gettempdir(), f"win_sec_{run_id}.png")

    @staticmethod
    def _wait_next_poll(poll_started: float, deadline: float) -> None:
        remaining = min(deadline, poll_started + _POLL_INTERVAL) - time.monotonic()
        if remaining > 0:
            time.sleep(remaining)

    @staticmethod
    def _same_fields(previous: list, current: list, tolerance: int = 8) -> bool:
        if len(previous) != len(current):
            return False
        return all(
            abs(old[0] - new[0]) <= tolerance
            and abs(old[1] - new[1]) <= tolerance
            and abs(old[2] - new[2]) <= tolerance
            and abs(old[3] - new[3]) <= tolerance
            for old, new in zip(previous, current)
        )

    @staticmethod
    def _same_rect(previous: dict | None, current: dict) -> bool:
        if not previous:
            return False
        return all(previous.get(key) == current.get(key) for key in ("id", "x", "y", "w", "h"))

    def wait_for_device_list(self, capam_ip: str, max_wait: int = 30) -> dict | None:
        """Chờ cửa sổ danh sách thiết bị CAPAM xuất hiện.
        Returns: rect dict hoặc None nếu timeout.
        """
        target_title = f"Symantec Privileged Access Manager Client - {capam_ip}"
        started = time.monotonic()
        deadline = started + max_wait
        while time.monotonic() < deadline:
            poll_started = time.monotonic()
            rect = self.adapter.get_window_rect(target_title)
            if rect:
                elapsed = time.monotonic() - started
                self._log(f"Đã phát hiện danh sách thiết bị sau {elapsed:.1f} giây.")
                return rect
            self._wait_next_poll(poll_started, deadline)
        self._log("Quá thời gian chờ danh sách thiết bị CAPAM.")
        return None

    def click_rdp(self, device_choice: str, capam_ip: str, max_wait: int = 30) -> bool:
        """Chụp cửa sổ CAPAM, tìm và click nút RDP cho thiết bị được chọn.
        Kiểm tra mỗi 0.5 giây trong tối đa max_wait giây.
        Returns: True nếu click thành công.
        """
        target_title = f"Symantec Privileged Access Manager Client - {capam_ip}"
        started = time.monotonic()
        deadline = started + max_wait
        previous_result = None
        previous_rect = None
        stable_count = 0
        next_detail_log = started
        while time.monotonic() < deadline:
            poll_started = time.monotonic()
            elapsed = time.monotonic() - started
            verbose = poll_started >= next_detail_log
            if verbose:
                self._log(f"Đang tìm nút RDP... ({elapsed:.1f}/{max_wait}s)")
                next_detail_log = poll_started + 2
            rect = self.adapter.get_window_rect(target_title)
            if not rect:
                self._wait_next_poll(poll_started, deadline)
                continue
            try:
                self.adapter.take_screenshot(rect, self._screenshot_tmp)
            except Exception as e:
                self._log(f"Lỗi chụp màn hình: {e}")
                self._wait_next_poll(poll_started, deadline)
                continue

            scene = cv2.imread(self._screenshot_tmp)
            try:
                os.remove(self._screenshot_tmp)
            except Exception:
                pass

            if scene is None:
                self._log("Không thể đọc ảnh cửa sổ CAPAM vừa chụp.")
                self._wait_next_poll(poll_started, deadline)
                continue

            result = find_device_rdp_button(
                scene, device_choice, log_fn=self._log if verbose else None
            )
            if result:
                unchanged = (
                    self._same_rect(previous_rect, rect)
                    and previous_result is not None
                    and abs(previous_result[0] - result[0]) <= 8
                    and abs(previous_result[1] - result[1]) <= 8
                )
                stable_count = stable_count + 1 if unchanged else 1
                previous_result = result
                previous_rect = rect.copy()
                if stable_count < 2:
                    self._wait_next_poll(poll_started, deadline)
                    continue
                current_rect = self.adapter.get_window_rect(target_title)
                if not self._same_rect(rect, current_rect or {}):
                    stable_count = 0
                    previous_result = None
                    previous_rect = None
                    continue
                if not self.adapter.focus_rect(rect):
                    stable_count = 0
                    continue
                current_rect = self.adapter.get_window_rect(target_title)
                if not self._same_rect(rect, current_rect or {}):
                    stable_count = 0
                    previous_result = None
                    previous_rect = None
                    continue
                click_x = rect["x"] + result[0]
                click_y = rect["y"] + result[1]
                self._log(f"Đang click nút RDP tại ({click_x}, {click_y})...")
                if not self.adapter.is_foreground(rect):
                    self._log("Foreground đổi trước click RDP; hủy click.")
                    stable_count = 0
                    continue
                pyautogui.click(click_x, click_y)
                return True
            stable_count = 0
            previous_result = None
            previous_rect = None
            self._wait_next_poll(poll_started, deadline)
        return False

    def fill_windows_security(self, username: str, password: str) -> bool:
        """Chờ và điền thông tin đăng nhập vào bảng Windows Security.
        Returns: True nếu hoàn tất.
        """
        self._log("Đang chờ bảng Windows Security xuất hiện...")
        rect = None
        window_title = None
        screenshot_tmp = self._win_sec_tmp

        started = time.monotonic()
        deadline = started + 30
        while time.monotonic() < deadline:
            for candidate_title in WIN_SEC_TITLES:
                rect = self.adapter.get_window_rect(candidate_title, exact=True)
                if rect:
                    window_title = candidate_title
                    elapsed = time.monotonic() - started
                    self._log(
                        f"Đã phát hiện bảng xác thực '{window_title}' sau {elapsed:.1f} giây."
                    )
                    break
            if rect:
                break
            time.sleep(min(_POLL_INTERVAL, max(0, deadline - time.monotonic())))

        if not rect:
            self._log("Không tìm thấy bảng xác thực RDP CAPAM trong 30 giây.")
            return False

        # Phát hiện ô nhập liệu trong bảng xác thực RDP CAPAM
        fields = []
        stable_count = 0
        previous_fields = []
        previous_rect = None
        started = time.monotonic()
        deadline = started + 15
        while time.monotonic() < deadline:
            poll_started = time.monotonic()
            try:
                current_rect = self.adapter.get_window_rect(window_title, exact=True)
                if not current_rect:
                    raise RuntimeError("Cửa sổ xác thực đã đóng.")
                rect = current_rect
                self.adapter.take_screenshot(rect, screenshot_tmp)
            except Exception:
                fields = []
                stable_count = 0
                previous_fields = []
                previous_rect = None
                self._wait_next_poll(poll_started, deadline)
                continue

            fields = detect_input_fields(screenshot_tmp, profile="windows_security")
            fields = [field for field in fields if field[2] >= rect["w"] * _MIN_FIELD_WIDTH_RATIO]
            try:
                os.remove(screenshot_tmp)
            except Exception:
                pass
            if len(fields) >= 1:
                unchanged = self._same_rect(previous_rect, rect) and self._same_fields(previous_fields, fields)
                stable_count = stable_count + 1 if unchanged else 1
                previous_fields = fields
                previous_rect = rect.copy()
            else:
                stable_count = 0
                previous_fields = []
                previous_rect = None
            if stable_count >= 2:
                break
            elapsed = time.monotonic() - started
            self._log(f"Đang chờ ô nhập liệu của bảng xác thực RDP CAPAM... ({elapsed:.1f}/15s)")
            self._wait_next_poll(poll_started, deadline)
            
        self._log(f"Bảng xác thực RDP CAPAM: Phát hiện thấy {len(fields)} ô nhập liệu.")

        if len(fields) < 1 or stable_count < 2:
            self._log("Không tìm thấy ô nhập liệu nào trong bảng xác thực RDP CAPAM.")
            return False

        if not self.adapter.focus_rect(rect):
            self._log("Không thể đưa overlay xác thực lên foreground trước khi nhập.")
            return False
        current_rect = self.adapter.get_window_rect(window_title, exact=True)
        if not self._same_rect(rect, current_rect or {}):
            self._log("Bảng xác thực đã di chuyển hoặc thay đổi; không nhập thông tin vào tọa độ cũ.")
            return False

        x0, y0, w0, h0 = fields[0]

        # Username
        pyautogui.click(rect["x"] + x0 + w0 // 2, rect["y"] + y0 + h0 // 2)
        time.sleep(0.15)
        if not self.adapter.is_foreground(rect):
            self._log("Foreground đổi sau click Username Windows Security; dừng nhập.")
            return False
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.1)
        write_text_safely(username)
        self._log(f"Đã nhập Username Windows Security: {username}")

        # Password
        time.sleep(0.2)
        if not self.adapter.is_foreground(rect):
            self._log("Foreground đổi trước khi nhập Password Windows Security; dừng nhập.")
            return False
        pyautogui.press("tab")
        time.sleep(0.15)
        if not self.adapter.is_foreground(rect):
            self._log("Foreground đổi sau Tab Windows Security; dừng nhập Password.")
            return False
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.1)
        write_text_safely(password)
        self._log("Đã nhập Password Windows Security.")

        time.sleep(0.3)
        if not self.adapter.is_foreground(rect):
            self._log("Foreground đã bị cửa sổ khác chiếm; không nhấn Enter Windows Security.")
            return False
        pyautogui.press("enter")
        self._log("Đã nhấn Login Windows Security — kết nối RDP đang thiết lập!")
        return True
