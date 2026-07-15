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
import time

import pyautogui

from adapters.base import OSAdapter
from vision.field_detector import detect_input_fields
from config import write_text_safely


CAPAM_WINDOW_TITLE = "Symantec Privileged Access Manager"

# Sau khi nhập IP và nhấn Connect, tiêu đề cửa sổ sẽ giữ nguyên
# nhưng giao diện bên trong chuyển sang màn hình Login
_LOGIN_SCREEN_WAIT = 8   # Tối đa giây chờ màn hình Login xuất hiện sau khi nhấn Connect


class CAPAMHandler:
    """Xử lý khởi động CAPAM Client và đăng nhập 2 bước (Address → Login)."""

    def __init__(self, adapter: OSAdapter, capam_ip: str, log_fn=None):
        self.adapter = adapter
        self.capam_ip = capam_ip
        self._log = log_fn or (lambda msg: None)
        self._screenshot_tmp = os.path.join(os.environ.get("TEMP", "/tmp"), "capam_crop.tmp.png")
        self._debug_address = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "debug_capam_address.png"
        )
        self._debug_login = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "debug_capam_login.png"
        )

    # ------------------------------------------------------------------
    # Khởi động
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Phát hiện ô nhập liệu
    # ------------------------------------------------------------------

    def _detect_fields(self, rect: dict, debug_path: str) -> list:
        """Chụp ảnh cửa sổ và phát hiện ô nhập liệu bằng OpenCV."""
        try:
            self.adapter.take_screenshot(rect, self._screenshot_tmp)
        except Exception:
            return []
        fields = detect_input_fields(
            self._screenshot_tmp,
            profile="capam",
            debug_output_path=debug_path,
        )
        try:
            os.remove(self._screenshot_tmp)
        except Exception:
            pass
        return fields

    # ------------------------------------------------------------------
    # Bước 1: Màn hình Address (Nhập IP)
    # ------------------------------------------------------------------

    def wait_for_address_screen(self, max_wait: int = 15) -> tuple[dict | None, list]:
        """Chờ màn hình Address của CAPAM xuất hiện với ít nhất 1 ô nhập.
        Returns: (rect, fields) hoặc (None, []) nếu timeout.
        """
        for attempt in range(max_wait):
            self.adapter.focus_window(CAPAM_WINDOW_TITLE)
            time.sleep(0.2)
            rect = self.adapter.get_window_rect(CAPAM_WINDOW_TITLE)
            if rect:
                ratio = rect["h"] / rect["w"]
                # Màn hình Address dẹt hơn (ratio ~0.45). Chỉ quét khi tỷ lệ nhỏ hơn 0.55
                if ratio < 0.55:
                    fields = self._detect_fields(rect, self._debug_address)
                    if len(fields) >= 1:
                        self._log(
                            f"[Address] Phát hiện {len(fields)} ô trên màn hình Address "
                            f"sau {attempt + 1} giây (Ratio: {ratio:.3f})."
                        )
                        return rect, fields
            self._log(f"Chờ màn hình Address CAPAM... ({attempt + 1}/{max_wait}s)")
            time.sleep(1)
        return None, []

    def enter_ip(self, rect: dict, fields: list) -> bool:
        """Điền địa chỉ IP vào ô Address đầu tiên và nhấn nút Connect.
        Ô đầu tiên (fields[0]) luôn là ô Address theo thứ tự từ trên xuống.
        Returns: True nếu thực hiện được.
        """
        if not fields:
            self._log("[Address] Không tìm thấy ô Address để nhập IP.")
            return False

        x0, y0, w0, h0 = fields[0]
        click_x = rect["x"] + x0 + w0 // 2
        click_y = rect["y"] + y0 + h0 // 2

        self._log(f"[Address] Điền IP '{self.capam_ip}' vào ô tại ({click_x}, {click_y}).")
        pyautogui.click(click_x, click_y)
        time.sleep(0.15)
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.1)
        pyautogui.press("backspace")
        time.sleep(0.1)
        write_text_safely(self.capam_ip)
        time.sleep(0.15)

        # Nhấn Enter thay vì tìm nút Connect để đơn giản và đáng tin cậy hơn
        pyautogui.press("enter")
        self._log(f"Đã nhập IP '{self.capam_ip}' và nhấn Connect. Chờ màn hình đăng nhập...")
        time.sleep(2.5)  # Chờ màn hình chuyển đổi sang trạng thái Login
        return True

    # ------------------------------------------------------------------
    # Bước 2: Màn hình Login (Username + Password)
    # ------------------------------------------------------------------

    def wait_for_login_screen(self, max_wait: int = 15) -> tuple[dict | None, list]:
        """Chờ màn hình Login xuất hiện với ít nhất 1 ô nhập.
        Phân biệt với màn hình Address bằng cách kiểm tra tỷ lệ khung hình.
        Returns: (rect, fields) hoặc (None, []) nếu timeout.
        """
        for attempt in range(max_wait):
            self.adapter.focus_window(CAPAM_WINDOW_TITLE)
            time.sleep(0.2)
            rect = self.adapter.get_window_rect(CAPAM_WINDOW_TITLE)
            if rect:
                ratio = rect["h"] / rect["w"]
                # Màn hình Login cao hơn (ratio ~0.65). Chỉ chấp nhận khi tỷ lệ >= 0.55
                if ratio >= 0.55:
                    fields = self._detect_fields(rect, self._debug_login)
                    if len(fields) >= 1:
                        self._log(
                            f"[Login] Màn hình đăng nhập sẵn sàng — {len(fields)} ô nhập liệu "
                            f"sau {attempt + 1} giây (Ratio: {ratio:.3f})."
                        )
                        return rect, fields
                else:
                    self._log(f"Vẫn là màn hình Address (Ratio: {ratio:.3f}). Chờ tải màn hình Login...")
            self._log(f"Chờ màn hình đăng nhập CAPAM... ({attempt + 1}/{max_wait}s)")
            time.sleep(1)
        return None, []

    def enter_credentials(self, rect: dict, fields: list, username: str, password: str) -> bool:
        """Điền tài khoản/mật khẩu vào màn hình Login CAPAM và nhấn Enter.
        fields[0] = Username, fields[1] = Password (sắp xếp từ trên xuống dưới).
        Returns: True nếu hoàn tất điền thông tin.
        """
        if len(fields) < 1:
            self._log("[Login] Không tìm thấy ô nhập liệu nào để điền thông tin CAPAM.")
            return False

        x0, y0, w0, h0 = fields[0]

        click_x0 = rect["x"] + x0 + w0 // 2
        click_y0 = rect["y"] + y0 + h0 // 2

        # Username
        pyautogui.click(click_x0, click_y0)
        time.sleep(0.1)
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.1)
        pyautogui.press("backspace")
        time.sleep(0.1)
        write_text_safely(username)
        self._log(f"[Login] Đã nhập tài khoản CAPAM: {username}")

        # Password (sử dụng phím TAB để chuyển ô, tránh lỗi OpenCV không nhận diện được ô có chứa sẵn dấu chấm đen)
        time.sleep(0.2)
        pyautogui.press("tab")
        time.sleep(0.1)
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.1)
        pyautogui.press("backspace")
        time.sleep(0.1)
        write_text_safely(password)
        self._log("[Login] Đã nhập mật khẩu CAPAM.")

        time.sleep(0.3)
        pyautogui.press("enter")
        self._log("[Login] Đã gửi thông tin đăng nhập CAPAM.")
        return True
