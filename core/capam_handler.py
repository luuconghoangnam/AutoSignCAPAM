"""
core/capam_handler.py — Xử lý luồng khởi động và đăng nhập CAPAM Client

Luồng 2 màn hình:
  1. Màn hình Address: Phát hiện >= 1 ô nhập → điền IP → nhấn Connect
  2. Màn hình Login:   Phát hiện >= 2 ô nhập → điền Username + Password → Enter

Tham khảo kiến trúc từ nhánh main (Linux) và cải tiến thêm:
  - Phân biệt màn hình Address vs Login dựa theo số lượng ô nhập
  - Không nhầm lẫn dropdown "Connect Mode" là ô nhập (lọc theo kích thước)
  - Clipboard paste để tránh bộ gõ tiếng Việt can thiệp
"""
import os
import tempfile
import time
import uuid

import pyautogui
import cv2

from adapters.base import OSAdapter
from vision.field_detector import detect_input_fields
from config import write_text_safely


CAPAM_WINDOW_TITLE = "Symantec Privileged Access Manager"
_POLL_INTERVAL = 0.5
_MIN_FIELD_WIDTH_RATIO = 0.25
_LOGIN_FIELD_WIDTH_RATIO = 0.18
_LOGIN_FIELD_MIN_WIDTH = 100
_STABLE_DETECTIONS = 2
_ADDRESS_FIELD_ROI = (0.38, 0.36, 0.80, 0.64)


class CAPAMHandler:
    """Xử lý khởi động CAPAM Client và đăng nhập 2 bước (Address → Login)."""

    def __init__(self, adapter: OSAdapter, capam_ip: str, log_fn=None, cancel_fn=None):
        self.adapter = adapter
        self.capam_ip = capam_ip
        self._log = log_fn or (lambda msg: None)
        self._cancelled = cancel_fn or (lambda: False)
        self._screenshot_tmp = os.path.join(
            tempfile.gettempdir(), f"capam_crop_{os.getpid()}_{uuid.uuid4().hex}.png"
        )

    # ------------------------------------------------------------------
    # Khởi động
    # ------------------------------------------------------------------

    def launch_and_wait(self, max_wait: int = 20) -> bool:
        """Khởi động CAPAM Client và chờ cửa sổ xuất hiện.
        Returns: True nếu tìm thấy cửa sổ trong thời gian chờ.
        """
        self._log("Đang khởi động CAPAM Client...")
        existing = self.adapter.get_capam_main_rect()
        if existing:
            self._log("CAPAM Client đã mở, dùng lại cửa sổ hiện có.")
            return True
        if not self.adapter.launch_capam():
            self._log("Không thể khởi động CAPAM Client.")
            return False
        started = time.monotonic()
        deadline = started + max_wait
        while time.monotonic() < deadline:
            if self._cancelled():
                return False
            rect = self.adapter.get_capam_main_rect()
            if rect:
                elapsed = time.monotonic() - started
                self._log(f"Đã phát hiện cửa sổ CAPAM Client sau {elapsed:.1f} giây.")
                return True
            elapsed = time.monotonic() - started
            self._log(f"Đang chờ CAPAM khởi động... ({elapsed:.1f}/{max_wait}s)")
            time.sleep(min(_POLL_INTERVAL, max(0, deadline - time.monotonic())))
        self._log("Quá thời gian chờ CAPAM Client xuất hiện.")
        return False

    # ------------------------------------------------------------------
    # Phát hiện ô nhập liệu
    # ------------------------------------------------------------------

    def _detect_fields(self, rect: dict) -> list:
        """Chụp ảnh cửa sổ và phát hiện ô nhập liệu bằng OpenCV."""
        try:
            self.adapter.take_screenshot(rect, self._screenshot_tmp)
        except Exception:
            return []
        fields = detect_input_fields(
            self._screenshot_tmp,
            profile="capam",
            debug_output_path=None,
        )
        try:
            os.remove(self._screenshot_tmp)
        except Exception:
            pass
        return fields

    def _detect_address_field(self, rect: dict) -> list:
        """Nhận diện ô Address; fallback theo ROI cố định của layout CAPAM."""
        fields = self._likely_text_fields(rect, self._detect_fields(rect))
        if fields:
            return fields

        try:
            self.adapter.take_screenshot(rect, self._screenshot_tmp)
            image = cv2.imread(self._screenshot_tmp)
        except Exception:
            image = None
        finally:
            try:
                os.remove(self._screenshot_tmp)
            except Exception:
                pass

        if image is None:
            return []

        image_h, image_w = image.shape[:2]
        x1 = int(image_w * _ADDRESS_FIELD_ROI[0])
        y1 = int(image_h * _ADDRESS_FIELD_ROI[1])
        x2 = int(image_w * _ADDRESS_FIELD_ROI[2])
        y2 = int(image_h * _ADDRESS_FIELD_ROI[3])
        roi = image[y1:y2, x1:x2]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        edges = cv2.Canny(blurred, 30, 100)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        candidates = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if image_w * 0.25 <= w <= image_w * 0.45 and 16 <= h <= 40:
                candidates.append((x1 + x, y1 + y, w, h))
        return sorted(candidates, key=lambda field: (field[1], field[0]))

    @staticmethod
    def _likely_text_fields(rect: dict, fields: list) -> list:
        """Loại nút và contour nhỏ; ô nhập trong các màn hình mẫu rộng >= 25% cửa sổ."""
        min_width = rect["w"] * _MIN_FIELD_WIDTH_RATIO
        return [field for field in fields if field[2] >= min_width]

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

    @staticmethod
    def _wait_next_poll(poll_started: float, deadline: float) -> None:
        remaining = min(deadline, poll_started + _POLL_INTERVAL) - time.monotonic()
        if remaining > 0:
            time.sleep(remaining)

    # ------------------------------------------------------------------
    # Bước 1: Màn hình Address (Nhập IP)
    # ------------------------------------------------------------------

    def wait_for_address_screen(self, max_wait: int = 30) -> tuple[dict | None, list]:
        """Chờ màn hình Address của CAPAM xuất hiện với ít nhất 1 ô nhập.
        Returns: (rect, fields) hoặc (None, []) nếu timeout.
        """
        started = time.monotonic()
        deadline = started + max_wait
        stable_count = 0
        previous_fields = []
        previous_rect = None
        while time.monotonic() < deadline:
            if self._cancelled():
                return None, []
            poll_started = time.monotonic()
            rect = self.adapter.get_capam_main_rect()
            if rect:
                ratio = rect["h"] / rect["w"]
                # Màn hình Address dẹt hơn (ratio ~0.45). Chỉ quét khi tỷ lệ nhỏ hơn 0.55
                if ratio < 0.55:
                    fields = self._detect_address_field(rect)
                    if len(fields) >= 1:
                        unchanged = self._same_rect(previous_rect, rect) and self._same_fields(previous_fields, fields)
                        stable_count = stable_count + 1 if unchanged else 1
                        previous_fields = fields
                        previous_rect = rect.copy()
                    else:
                        stable_count = 0
                        previous_fields = []
                        previous_rect = None
                    if stable_count >= _STABLE_DETECTIONS:
                        elapsed = time.monotonic() - started
                        self._log(
                            f"[Address] Phát hiện {len(fields)} ô trên màn hình Address "
                            f"ổn định sau {elapsed:.1f} giây (Ratio: {ratio:.3f})."
                        )
                        return rect, fields
                else:
                    stable_count = 0
                    previous_fields = []
                    previous_rect = None
            elapsed = time.monotonic() - started
            self._log(f"Chờ màn hình Address CAPAM... ({elapsed:.1f}/{max_wait}s)")
            self._wait_next_poll(poll_started, deadline)
        return None, []

    def enter_ip(self, rect: dict, fields: list) -> bool:
        """Điền địa chỉ IP vào ô Address đầu tiên và nhấn nút Connect.
        Ô đầu tiên (fields[0]) luôn là ô Address theo thứ tự từ trên xuống.
        Returns: True nếu thực hiện được.
        """
        if not fields:
            self._log("[Address] Không tìm thấy ô Address để nhập IP.")
            return False

        for attempt in range(3):
            if attempt > 0:
                self._log(f"[Address] Thử lại nhập IP lần {attempt + 1}...")

            if not self.adapter.focus_rect(rect):
                self._log("[Address] Không thể đưa CAPAM lên foreground trước khi nhập.")
                time.sleep(0.5)
                continue
            current_rect = self.adapter.get_window_rect_for_hwnd(rect.get("id"))
            if not current_rect or any(
                rect.get(key) != current_rect.get(key) for key in ("id", "w", "h")
            ):
                self._log("[Address] Cửa sổ đã thay đổi kích thước hoặc instance; hủy thao tác cũ.")
                return False
            rect = current_rect

            x0, y0, w0, h0 = fields[0]
            click_x = rect["x"] + x0 + w0 // 2
            click_y = rect["y"] + y0 + h0 // 2

            self._log(f"[Address] Điền IP '{self.capam_ip}' vào ô tại ({click_x}, {click_y}).")
            pyautogui.click(click_x, click_y)
            time.sleep(0.05)
            if not self.adapter.is_foreground(rect):
                self._log("[Address] Foreground đổi sau click; dừng nhập IP.")
                return False
            pyautogui.hotkey("ctrl", "a")
            time.sleep(0.05)
            pyautogui.press("backspace")
            time.sleep(0.05)
            if not write_text_safely(self.capam_ip, lambda: self.adapter.is_foreground(rect)):
                return False
            time.sleep(0.1)

            # Giữ focus trong ô Address rồi Enter; không click nút theo tọa độ để
            # tránh nhầm nút Cancel khi layout CAPAM thay đổi.
            pyautogui.click(click_x, click_y)
            time.sleep(0.05)
            if not self.adapter.is_foreground(rect):
                self._log("[Address] Foreground đổi; không nhấn Enter.")
                return False
            pyautogui.press("enter")
            self._log(
                f"Đã xóa và nhập lại IP '{self.capam_ip}', nhấn Enter trong ô Address. "
                "Chờ màn hình đăng nhập..."
            )
            time.sleep(0.25)
            return True
            
        self._log("[Address] Thất bại sau 3 lần thử nhập IP.")
        return False

    # ------------------------------------------------------------------
    # Bước 2: Màn hình Login (Username + Password)
    # ------------------------------------------------------------------

    def wait_for_login_screen(self, max_wait: int = 30) -> tuple[dict | None, list]:
        """Chờ màn hình Login xuất hiện với ít nhất 1 ô nhập.
        Phân biệt với màn hình Address bằng cách kiểm tra tỷ lệ khung hình.
        Returns: (rect, fields) hoặc (None, []) nếu timeout.
        """
        started = time.monotonic()
        deadline = started + max_wait
        stable_count = 0
        previous_fields = []
        previous_rect = None
        while time.monotonic() < deadline:
            if self._cancelled():
                return None, []
            poll_started = time.monotonic()
            rect = self.adapter.get_capam_main_rect()
            if rect:
                ratio = rect["h"] / rect["w"]
                # Màn hình Login cao hơn (ratio ~0.65). Chỉ chấp nhận khi tỷ lệ >= 0.55
                if ratio >= 0.55:
                    raw_fields = self._detect_fields(rect)
                    min_width = max(_LOGIN_FIELD_MIN_WIDTH, rect["w"] * _LOGIN_FIELD_WIDTH_RATIO)
                    fields = [field for field in raw_fields if field[2] >= min_width]
                    if raw_fields and not fields:
                        self._log(
                            f"[Login] Có contour nhưng field quá hẹp: "
                            f"{raw_fields}; đang chờ frame ổn định tiếp theo."
                        )
                    if len(fields) >= 1:
                        unchanged = self._same_rect(previous_rect, rect) and self._same_fields(previous_fields, fields)
                        stable_count = stable_count + 1 if unchanged else 1
                        previous_fields = fields
                        previous_rect = rect.copy()
                    else:
                        stable_count = 0
                        previous_fields = []
                        previous_rect = None
                    if stable_count >= _STABLE_DETECTIONS:
                        elapsed = time.monotonic() - started
                        self._log(
                            f"[Login] Màn hình đăng nhập ổn định - {len(fields)} ô nhập liệu "
                            f"sau {elapsed:.1f} giây (Ratio: {ratio:.3f})."
                        )
                        return rect, fields
                else:
                    stable_count = 0
                    previous_fields = []
                    previous_rect = None
                    self._log(f"Vẫn là màn hình Address (Ratio: {ratio:.3f}). Chờ tải màn hình Login...")
            elapsed = time.monotonic() - started
            self._log(f"Chờ màn hình đăng nhập CAPAM... ({elapsed:.1f}/{max_wait}s)")
            self._wait_next_poll(poll_started, deadline)
        return None, []

    def enter_credentials(self, rect: dict, fields: list, username: str, password: str) -> bool:
        """Điền tài khoản/mật khẩu vào màn hình Login CAPAM và nhấn Enter.
        fields[0] = Username, fields[1] = Password (sắp xếp từ trên xuống dưới).
        Returns: True nếu hoàn tất điền thông tin.
        """
        if len(fields) < 1:
            self._log("[Login] Không tìm thấy ô nhập liệu nào để điền thông tin CAPAM.")
            return False

        for attempt in range(3):
            if attempt > 0:
                self._log(f"[Login] Thử lại đăng nhập CAPAM lần {attempt + 1}...")

            if not self.adapter.focus_rect(rect):
                self._log("[Login] Không thể đưa CAPAM lên foreground trước khi nhập.")
                time.sleep(0.5)
                continue
            current_rect = self.adapter.get_window_rect_for_hwnd(rect.get("id"))
            if not current_rect or any(
                rect.get(key) != current_rect.get(key) for key in ("id", "w", "h")
            ):
                self._log("[Login] Cửa sổ đã thay đổi kích thước hoặc instance; hủy thao tác cũ.")
                return False
            rect = current_rect

            x0, y0, w0, h0 = fields[0]

            click_x0 = rect["x"] + x0 + w0 // 2
            click_y0 = rect["y"] + y0 + h0 // 2

            # Username
            pyautogui.click(click_x0, click_y0)
            time.sleep(0.1)
            if not self.adapter.is_foreground(rect):
                self._log("[Login] Foreground đổi sau click Username; dừng nhập.")
                return False
            pyautogui.hotkey("ctrl", "a")
            time.sleep(0.1)
            pyautogui.press("backspace")
            time.sleep(0.1)
            if not write_text_safely(username, lambda: self.adapter.is_foreground(rect)):
                return False
            self._log(f"[Login] Đã nhập tài khoản CAPAM: {username}")

            # Password (sử dụng phím TAB để chuyển ô, tránh lỗi OpenCV không nhận diện được ô có chứa sẵn dấu chấm đen)
            # CAPAM runs on Java Swing; let its event queue finish processing
            # the username paste before changing focus.
            time.sleep(0.45)
            if not self.adapter.is_foreground(rect):
                return False
            pyautogui.keyDown("tab")
            time.sleep(0.12)
            pyautogui.keyUp("tab")
            time.sleep(0.5)
            if not self.adapter.is_foreground(rect):
                self._log("[Login] Foreground đổi sau Tab; dừng nhập Password.")
                return False
            pyautogui.hotkey("ctrl", "a")
            time.sleep(0.2)
            pyautogui.press("backspace")
            time.sleep(0.2)
            if not write_text_safely(password, lambda: self.adapter.is_foreground(rect)):
                return False
            self._log("[Login] Đã nhập mật khẩu CAPAM.")

            time.sleep(0.3)
            if not self.adapter.is_foreground(rect):
                self._log("[Login] Foreground đổi; không gửi Enter.")
                return False
            pyautogui.press("enter")
            self._log("[Login] Đã gửi thông tin đăng nhập CAPAM.")
            return True

        self._log("[Login] Thất bại sau 3 lần thử đăng nhập CAPAM.")
        return False
