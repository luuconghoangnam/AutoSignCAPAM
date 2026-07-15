"""
core/state_machine.py — FSM điều phối toàn bộ luồng tự động hóa

Thay thế vòng lặp lồng nhau trong main_automation.py bằng Finite State Machine.
Mỗi state là một phương thức riêng biệt trả về state tiếp theo.
"""
import time

import pyautogui
from PyQt5.QtCore import QThread, pyqtSignal

from adapters import get_os_adapter
from core.gp_handler import GPHandler, STATE_PORTAL, STATE_CREDENTIALS, STATE_CONNECTED, STATE_AUTH_FAILED, STATE_UNKNOWN
from core.capam_handler import CAPAMHandler
from core.rdp_handler import RDPHandler


class AutomationWorker(QThread):
    """QThread chạy FSM ở background, emit log_signal và finished_signal về UI."""

    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool)

    def __init__(self, username: str, password_prefix: str, otp: str,
                 server_choice: str, capam_ip: str):
        super().__init__()
        self.username = username
        self.password_prefix = password_prefix
        self.otp = otp
        self.server_choice = server_choice  # "200", "12", or "none"
        self.capam_ip = capam_ip

        self._adapter = get_os_adapter()
        self._gp = GPHandler(self._adapter, log_fn=self._log)
        self._capam = CAPAMHandler(self._adapter, capam_ip, log_fn=self._log)
        self._rdp = RDPHandler(self._adapter, log_fn=self._log)

    def _log(self, msg: str) -> None:
        self.log_signal.emit(f"[*] {msg}")

    # ------------------------------------------------------------------
    # FSM States
    # ------------------------------------------------------------------

    def _state_check_vpn(self) -> str:
        """State 1: Kiểm tra xem VPN đã kết nối sẵn chưa."""
        self._log(f"Kiểm tra kết nối VPN tới CAPAM ({self.capam_ip})...")
        if self._gp.is_already_connected(self.capam_ip):
            self._log("VPN đã kết nối sẵn. Bỏ qua bước đăng nhập GlobalProtect.")
            return "CAPAM_LAUNCH"
        return "GP_START"

    def _state_gp_start(self) -> str:
        """State 2a: Khởi động UI GlobalProtect và ghi nhận log offset."""
        self._log("Bắt đầu kích hoạt GlobalProtect...")
        self._gp.init_log_offset()
        self._adapter.launch_gp_ui()
        time.sleep(1.5)
        self._adapter.focus_window("GlobalProtect", exact=True)
        return "GP_DETECT"

    def _state_gp_detect(self, attempt: int) -> str:
        """State 2b: Phát hiện trạng thái màn hình GP."""
        self._log(f"Cố gắng đăng nhập GlobalProtect lần {attempt}...")

        rect = self._gp.ensure_window_visible()
        if not rect:
            self._log("Không tìm thấy cửa sổ GlobalProtect sau khi kích hoạt lại.")
            return "GP_DETECT"

        # Đọc trạng thái từ log (toàn bộ lần đầu, sau đó chỉ log mới)
        state = self._gp.read_state(read_all=(attempt == 1))
        self._log(f"Trạng thái GP từ log: {state}")

        # Fallback sang OpenCV nếu log chưa phản ánh kịp
        fields = self._gp.detect_fields(rect)
        self._log(f"OpenCV phát hiện {len(fields)} ô nhập liệu.")

        if state == STATE_UNKNOWN:
            if len(fields) == 1:
                state = STATE_PORTAL
            elif len(fields) >= 2:
                state = STATE_CREDENTIALS

        if state == STATE_PORTAL:
            self._gp.enter_portal_url(rect, fields)
            self._log("Đã kết nối Portal. Chờ chuyển trang đăng nhập (5 giây)...")
            time.sleep(5)
            self._adapter.focus_window("GlobalProtect", exact=True)
            return "GP_DETECT"

        elif state == STATE_CREDENTIALS:
            full_password = self.password_prefix + self.otp
            self._gp.enter_credentials(rect, fields, self.username, full_password)
            self._gp.mark_log_before_submit()
            self._log("Gửi thông tin đăng nhập GlobalProtect...")
            pyautogui.press("enter")
            return "GP_WAIT_CONNECT"

        elif state == STATE_CONNECTED:
            self._log("GlobalProtect đã kết nối thành công từ trước.")
            return "CAPAM_LAUNCH"

        elif state == STATE_AUTH_FAILED:
            return "GP_AUTH_FAILED"

        return "GP_DETECT"

    def _state_gp_wait_connect(self) -> str:
        """State 2c: Chờ VPN kết nối hoặc phát hiện lỗi xác thực."""
        self._log("Đang chờ xác minh kết nối VPN...")
        result = self._gp.wait_connected_or_fail(self.capam_ip, timeout_sec=25)
        if result == "CONNECTED":
            self._log("GlobalProtect đã kết nối VPN thành công!")
            return "CAPAM_LAUNCH"
        elif result == "AUTH_FAILED":
            return "GP_AUTH_FAILED"
        else:
            self._log("Hết thời gian chờ kết nối VPN.")
            return "GP_TIMEOUT"

    def _state_capam_launch(self) -> str:
        """State 3: Khởi động CAPAM Client."""
        self._log("Đang khởi động Broadcom CAPAM Client...")
        if not self._capam.launch_and_wait():
            self._log("Không tìm thấy cửa sổ CAPAM Client. Tiếp tục với bước đăng nhập thủ công.")
        return "CAPAM_LOGIN"

    def _state_capam_login(self) -> str:
        """State 4: Đăng nhập CAPAM."""
        rect, fields = self._capam.wait_for_login_screen()
        if not rect:
            self._log("Lỗi: Không tìm thấy màn hình đăng nhập CAPAM.")
            return "ERROR"
        self._adapter.focus_window("Symantec Privileged Access Manager")
        time.sleep(0.5)
        success = self._capam.enter_credentials(
            rect, fields, self.username, self.password_prefix
        )
        if not success:
            return "ERROR"
        if self.server_choice == "none":
            return "DONE"
        return "RDP_WAIT_LIST"

    def _state_rdp_wait_list(self) -> str:
        """State 5a: Chờ danh sách thiết bị CAPAM xuất hiện."""
        rect = self._rdp.wait_for_device_list(self.capam_ip)
        if not rect:
            return "ERROR"
        self._adapter.focus_window(f"Symantec Privileged Access Manager Client - {self.capam_ip}")
        time.sleep(1.5)
        return "RDP_CLICK"

    def _state_rdp_click(self) -> str:
        """State 5b: Tìm và click nút RDP."""
        self._log(f"Đang tìm và click nút RDP cho thiết bị {self.server_choice}...")
        if not self._rdp.click_rdp(self.server_choice):
            self._log("Không tìm thấy nút RDP trong thời gian chờ.")
            return "ERROR"
        return "WINDOWS_SECURITY"

    def _state_windows_security(self) -> str:
        """State 6: Điền thông tin vào bảng Windows Security."""
        self._rdp.fill_windows_security(self.username, self.password_prefix)
        return "DONE"

    # ------------------------------------------------------------------
    # FSM Runner
    # ------------------------------------------------------------------

    def run(self) -> None:
        pyautogui.PAUSE = 0.1
        state = "CHECK_VPN"
        gp_attempts = 0

        while True:
            if state == "CHECK_VPN":
                state = self._state_check_vpn()

            elif state == "GP_START":
                state = self._state_gp_start()

            elif state == "GP_DETECT":
                gp_attempts += 1
                if gp_attempts > 4:
                    self._log("Quá số lần thử đăng nhập GlobalProtect (4 lần). Dừng lại.")
                    self.finished_signal.emit(False)
                    return
                state = self._state_gp_detect(gp_attempts)

            elif state == "GP_WAIT_CONNECT":
                state = self._state_gp_wait_connect()

            elif state == "GP_AUTH_FAILED":
                self._log("[LỖI] Sai tài khoản, mật khẩu hoặc mã OTP GlobalProtect!")
                self.finished_signal.emit(False)
                return

            elif state == "GP_TIMEOUT":
                self._log("[LỖI] Quá thời gian kết nối VPN. Đăng nhập GP thất bại.")
                self.finished_signal.emit(False)
                return

            elif state == "CAPAM_LAUNCH":
                state = self._state_capam_launch()

            elif state == "CAPAM_LOGIN":
                state = self._state_capam_login()

            elif state == "RDP_WAIT_LIST":
                state = self._state_rdp_wait_list()

            elif state == "RDP_CLICK":
                state = self._state_rdp_click()

            elif state == "WINDOWS_SECURITY":
                state = self._state_windows_security()

            elif state == "DONE":
                self._log("==> KỊCH BẢN TỰ ĐỘNG HÓA HOÀN TẤT! <==")
                self.finished_signal.emit(True)
                return

            elif state == "ERROR":
                self._log("[LỖI] Kịch bản tự động hóa kết thúc do lỗi.")
                self.finished_signal.emit(False)
                return

            else:
                self._log(f"[LỖI] Trạng thái không xác định: {state}")
                self.finished_signal.emit(False)
                return
