"""
core/state_machine.py — FSM điều phối toàn bộ luồng tự động hóa

Thay thế vòng lặp lồng nhau trong main_automation.py bằng Finite State Machine.
Mỗi state là một phương thức riêng biệt trả về state tiếp theo.
"""
import time

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
        self._gp_visual_state = STATE_UNKNOWN
        self._gp_visual_count = 0
        self._gp_portal_submitted_at = 0.0
        self._capam_launched_early = False

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

    def _state_reset_capam(self) -> str:
        """Đóng CAPAM cũ để mỗi lượt automation bắt đầu từ màn hình Address."""
        capam_rect = self._adapter.get_window_rect("Symantec Privileged Access Manager")
        if not capam_rect:
            return "CHECK_VPN"

        self._log("Đang đóng phiên CAPAM cũ để bắt đầu lại từ đầu...")
        if not self._adapter.kill_window_process(capam_rect):
            self._log("Không xác định được process của phiên CAPAM cũ.")
            return "ERROR"
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if not self._adapter.get_window_rect("Symantec Privileged Access Manager"):
                self._log("Đã đóng phiên CAPAM cũ.")
                return "CHECK_VPN"
            time.sleep(0.2)

        self._log("Không thể đóng phiên CAPAM cũ trong 5 giây.")
        return "ERROR"

    def _state_gp_start(self) -> str:
        """State 2a: Khởi động UI GlobalProtect và ghi nhận log offset."""
        self._log("Bắt đầu kích hoạt GlobalProtect...")
        self._gp.init_log_offset()
        if not self._adapter.launch_gp_ui():
            self._log("Không tìm thấy hoặc không thể kích hoạt GlobalProtect.")
            return "ERROR"
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

        # Xác định trạng thái màn hình dựa vào thực tế số lượng ô nhập nhận diện được trên UI
        if len(fields) == 1:
            visual_state = STATE_PORTAL
        elif len(fields) >= 2:
            visual_state = STATE_CREDENTIALS
        else:
            visual_state = STATE_UNKNOWN
            # Chỉ dùng trạng thái từ log khi OpenCV không phát hiện được ô nhập nào
            if state == STATE_UNKNOWN or (state == STATE_AUTH_FAILED and attempt == 1):
                state = STATE_UNKNOWN

        if visual_state != STATE_UNKNOWN:
            if visual_state == self._gp_visual_state:
                self._gp_visual_count += 1
            else:
                self._gp_visual_state = visual_state
                self._gp_visual_count = 1
            if self._gp_visual_count < 2:
                self._log(f"Màn hình GP {visual_state} cần thêm 1 frame xác nhận.")
                time.sleep(0.5)
                return "GP_DETECT"
            state = visual_state
        else:
            self._gp_visual_state = STATE_UNKNOWN
            self._gp_visual_count = 0

        if state == STATE_PORTAL:
            now = time.monotonic()
            if now - self._gp_portal_submitted_at < 5:
                time.sleep(0.5)
                return "GP_DETECT"
            if not self._gp.enter_portal_url(rect, fields):
                time.sleep(0.5)
                return "GP_DETECT"
            self._gp_portal_submitted_at = now
            self._log("Đã kết nối Portal. Poll màn hình đăng nhập mỗi 0.5 giây...")
            time.sleep(0.5)
            return "GP_DETECT"

        elif state == STATE_CREDENTIALS:
            full_password = self.password_prefix + self.otp
            if not self._gp.enter_credentials(rect, fields, self.username, full_password):
                time.sleep(0.5)
                return "GP_DETECT"
            self._gp.mark_log_before_submit()
            self._log("Gửi thông tin đăng nhập GlobalProtect...")
            if not self._gp.submit_credentials(rect):
                time.sleep(0.5)
                return "GP_DETECT"

            self._log("Đang khởi động sớm CAPAM Client để tiết kiệm thời gian chờ VPN...")
            if self._adapter.launch_capam():
                self._capam_launched_early = True
                # CAPAM may claim foreground while starting; restore GP before polling VPN.
                self._adapter.focus_rect(rect)

            return "GP_WAIT_CONNECT"

        elif state == STATE_CONNECTED:
            self._log("GlobalProtect đã kết nối thành công từ trước.")
            return "CAPAM_LAUNCH"

        elif state == STATE_AUTH_FAILED:
            return "GP_AUTH_FAILED"

        time.sleep(0.5)
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
        self._log("Đang chuẩn bị phiên CAPAM Client...")

        if getattr(self, "_capam_launched_early", False):
            started = time.monotonic()
            while time.monotonic() < started + 20:
                if self._adapter.get_window_rect("Symantec Privileged Access Manager"):
                    return "CAPAM_ADDRESS"
                time.sleep(0.5)
            self._log("Lỗi: Quá thời gian chờ CAPAM Client xuất hiện.")
            return "ERROR"
        else:
            if not self._capam.launch_and_wait():
                self._log("Không tìm thấy hoặc không thể khởi động CAPAM Client.")
                return "ERROR"

        return "CAPAM_ADDRESS"

    def _state_capam_address(self) -> str:
        """State 3b: Nhập IP trên màn hình Address của CAPAM."""
        capam_rect = self._adapter.get_window_rect("Symantec Privileged Access Manager")
        if not capam_rect:
            self._log("Lỗi: Cửa sổ CAPAM chưa xuất hiện sau khi VPN kết nối.")
            return "ERROR"
        if not self._adapter.focus_rect(capam_rect):
            self._log("Lỗi: Không thể đưa cửa sổ CAPAM lên foreground để nhận diện Address.")
            return "ERROR"
        self._log("Đã đưa đúng cửa sổ CAPAM lên foreground; bắt đầu nhận diện ô Address...")
        time.sleep(0.2)

        self._log(f"Đang chờ màn hình Address CAPAM để nhập IP '{self.capam_ip}'...")
        rect, fields = self._capam.wait_for_address_screen()
        if not rect:
            self._log("Lỗi: Không tìm thấy màn hình Address của CAPAM.")
            return "ERROR"
        if rect.get("id") != capam_rect.get("id"):
            self._log("Lỗi: Instance CAPAM thay đổi trong lúc nhận diện; không dùng tọa độ cũ.")
            return "ERROR"
        success = self._capam.enter_ip(rect, fields)
        if not success:
            return "ERROR"
        return "CAPAM_LOGIN"

    def _state_capam_login(self) -> str:
        """State 4: Chờ màn hình Login và điền Username + Password."""
        self._log("Đang chờ màn hình đăng nhập CAPAM (Username + Password)...")
        rect, fields = self._capam.wait_for_login_screen()
        if not rect:
            self._log("Lỗi: Không tìm thấy màn hình đăng nhập CAPAM.")
            return "ERROR"
        success = self._capam.enter_credentials(
            rect, fields, self.username, self.password_prefix + self.otp
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
        return "RDP_CLICK"

    def _state_rdp_click(self) -> str:
        """State 5b: Tìm và click nút RDP."""
        self._log(f"Đang tìm và click nút RDP cho thiết bị {self.server_choice}...")
        if not self._rdp.click_rdp(self.server_choice, self.capam_ip):
            self._log("Không tìm thấy nút RDP trong thời gian chờ.")
            return "ERROR"
        return "WINDOWS_SECURITY"

    def _state_windows_security(self) -> str:
        """State 6: Điền thông tin vào bảng Windows Security."""
        if self._rdp.fill_windows_security(self.username, self.password_prefix):
            return "DONE"
        self._log("Không thể hoàn tất bảng xác thực RDP CAPAM.")
        return "ERROR"

    # ------------------------------------------------------------------
    # FSM Runner
    # ------------------------------------------------------------------

    def run(self) -> None:
        import pyautogui
        pyautogui.PAUSE = 0.1
        state = "RESET_CAPAM"
        gp_attempts = 0

        while True:
            if state == "RESET_CAPAM":
                state = self._state_reset_capam()

            elif state == "CHECK_VPN":
                state = self._state_check_vpn()

            elif state == "GP_START":
                state = self._state_gp_start()

            elif state == "GP_DETECT":
                gp_attempts += 1
                if gp_attempts > 60:
                    self._log("Không nhận diện được GlobalProtect trong 30 giây. Dừng lại.")
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

            elif state == "CAPAM_ADDRESS":
                state = self._state_capam_address()

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
