"""
ui/main_window.py — Giao diện người dùng PyQt5 chính

Kết nối với AutomationWorker qua signals.
Tự động lưu/tải cài đặt người dùng.
Thu nhỏ cửa sổ khi chạy tự động để không che khuất CAPAM/GP.
"""
import os
import json

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QRadioButton, QButtonGroup, QTextEdit, QCheckBox,
)
from PyQt5.QtCore import Qt, QRegularExpression, QTimer
from PyQt5.QtGui import QFont, QRegularExpressionValidator, QIcon

from config import CAPAM_IP_DEFAULT, get_resource_path
from core.state_machine import AutomationWorker

SETTINGS_FILE = os.path.expanduser("~/.capam_autosign_settings.json")

# Absolute paths to indicator images for QSS styling
_radio_unchecked = get_resource_path("ui/radio_unchecked.png").replace("\\", "/")
_radio_checked = get_resource_path("ui/radio_checked.png").replace("\\", "/")
_checkbox_unchecked = get_resource_path("ui/checkbox_unchecked.png").replace("\\", "/")
_checkbox_checked = get_resource_path("ui/checkbox_checked.png").replace("\\", "/")

_STYLESHEET = f"""
    QMainWindow {{ background-color: #1e1e2e; }}
    QLabel {{ color: #a6adc8; font-size: 12px; font-weight: bold; }}
    QLineEdit {{
        background-color: #24253a; color: #cdd6f4;
        border: 2px solid #45475a; border-radius: 8px;
        padding: 5px 8px; font-size: 13px; font-weight: normal; min-height: 24px;
    }}
    QLineEdit#otp_input {{
        font-size: 26px; font-weight: bold; letter-spacing: 8px; min-height: 42px;
        border: 2px solid #f38ba8; background-color: #1e1e2e; color: #f38ba8;
    }}
    QLineEdit:focus {{ border: 2px solid #89b4fa; background-color: #2b2c45; }}
    QLineEdit#otp_input:focus {{ border: 2px solid #eba0ac; }}
    
    QRadioButton {{ color: #cdd6f4; font-size: 12px; spacing: 8px; }}
    QRadioButton::indicator {{ width: 18px; height: 18px; }}
    QRadioButton::indicator::unchecked {{ image: url({_radio_unchecked}); }}
    QRadioButton::indicator::checked {{ image: url({_radio_checked}); }}
    
    QCheckBox {{ color: #cdd6f4; font-size: 12px; spacing: 8px; }}
    QCheckBox::indicator {{ width: 18px; height: 18px; }}
    QCheckBox::indicator::unchecked {{ image: url({_checkbox_unchecked}); }}
    QCheckBox::indicator::checked {{ image: url({_checkbox_checked}); }}
    
    QPushButton {{
        background-color: #89b4fa; color: #1e1e2e;
        font-size: 13px; font-weight: bold; border-radius: 8px; padding: 10px;
        border: none;
    }}
    QPushButton:hover {{ background-color: #b4befe; }}
    QPushButton:pressed {{ background-color: #74c7ec; }}
    QPushButton:disabled {{ background-color: #313244; color: #585b70; }}
    QPushButton#btn_cancel {{ background-color: #f38ba8; color: #1e1e2e; }}
    QPushButton#btn_cancel:hover {{ background-color: #eba0ac; }}
    QPushButton#btn_cancel:pressed {{ background-color: #e64553; }}
    QPushButton#btn_cancel:disabled {{ background-color: #313244; color: #585b70; }}
    
    QTextEdit {{
        background-color: #11111b; color: #a6e3a1;
        border: 2px solid #313244; border-radius: 8px; padding: 8px;
        font-family: 'Consolas', 'Monospace', 'Courier New'; font-size: 11px;
    }}
    
    QScrollBar:vertical {{
        border: none;
        background: #11111b;
        width: 10px;
        margin: 0px;
    }}
    QScrollBar::handle:vertical {{
        background: #45475a;
        min-height: 20px;
        border-radius: 5px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: #585b70;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        border: none; background: none; height: 0px;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: none;
    }}
"""


def apply_dark_title_bar(window: QMainWindow) -> None:
    import platform
    if platform.system() == "Windows":
        try:
            import ctypes
            hwnd = int(window.winId())
            rendering = ctypes.c_int(1)
            # DWMWA_USE_IMMERSIVE_DARK_MODE: 20 for Windows 11, 19 for Windows 10
            for attr in (20, 19):
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attr, ctypes.byref(rendering), ctypes.sizeof(rendering)
                )
        except Exception:
            pass


def clear_topmost(window: QMainWindow) -> None:
    """Keep controller below target apps even if prior focus calls left it topmost."""
    import platform
    if platform.system() != "Windows":
        return
    try:
        import ctypes

        hwnd = int(window.winId())
        # HWND_NOTOPMOST; SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE | SWP_FRAMECHANGED
        ctypes.windll.user32.SetWindowPos(
            hwnd, -2, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010 | 0x0020
        )
    except Exception:
        pass


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.worker: AutomationWorker | None = None
        self._init_ui()
        self._load_settings()
        QTimer.singleShot(0, self.txt_otp.setFocus)

    # ------------------------------------------------------------------
    # UI Initialization
    # ------------------------------------------------------------------

    def _init_ui(self) -> None:
        self.setWindowTitle("CAPAM AutoSign")
        self.setFixedSize(480, 560)
        self.setStyleSheet(_STYLESHEET)

        # Apply dark title bar (Windows 10/11)
        apply_dark_title_bar(self)
        clear_topmost(self)

        # Set Window Icon
        icon_path = get_resource_path("ui/icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(8)
        layout.setContentsMargins(16, 14, 16, 14)

        # --- Hàng 1: Tài khoản | Mật khẩu | IP ---
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        v_user = QVBoxLayout()
        v_user.setSpacing(3)
        v_user.addWidget(QLabel("Tài khoản:"))
        self.txt_username = QLineEdit()
        self.txt_username.setObjectName("username_input")
        self.txt_username.setPlaceholderText("username")
        v_user.addWidget(self.txt_username)

        v_pass = QVBoxLayout()
        v_pass.setSpacing(3)
        h_pass_lbl = QHBoxLayout()
        h_pass_lbl.addWidget(QLabel("Mật khẩu:"))
        self.chk_show_pass = QCheckBox("Hiện")
        self.chk_show_pass.stateChanged.connect(self._toggle_password)
        h_pass_lbl.addWidget(self.chk_show_pass)
        h_pass_lbl.addStretch()
        v_pass.addLayout(h_pass_lbl)
        self.txt_pass_prefix = QLineEdit()
        self.txt_pass_prefix.setObjectName("password_prefix_input")
        self.txt_pass_prefix.setEchoMode(QLineEdit.Password)
        self.txt_pass_prefix.setPlaceholderText("mật khẩu")
        v_pass.addWidget(self.txt_pass_prefix)

        v_ip = QVBoxLayout()
        v_ip.setSpacing(3)
        v_ip.addWidget(QLabel("IP CAPAM:"))
        self.txt_capam_ip = QLineEdit()
        self.txt_capam_ip.setObjectName("capam_ip_input")
        self.txt_capam_ip.setText(CAPAM_IP_DEFAULT)
        self.txt_capam_ip.setPlaceholderText("10.x.x.x")
        v_ip.addWidget(self.txt_capam_ip)

        row1.addLayout(v_user, 3)
        row1.addLayout(v_pass, 3)
        row1.addLayout(v_ip, 2)
        layout.addLayout(row1)

        # --- OTP ---
        layout.addWidget(QLabel("Nhập mã OTP (6 chữ số) rồi nhấn Enter:"))
        self.txt_otp = QLineEdit()
        self.txt_otp.setObjectName("otp_input")
        self.txt_otp.setMaxLength(6)
        self.txt_otp.setValidator(
            QRegularExpressionValidator(QRegularExpression(r"\d{0,6}"), self.txt_otp)
        )
        self.txt_otp.setAlignment(Qt.AlignCenter)
        self.txt_otp.setPlaceholderText("______")
        self.txt_otp.returnPressed.connect(self.start_automation)
        layout.addWidget(self.txt_otp)

        # --- Chọn máy chủ ---
        layout.addWidget(QLabel("Kết nối máy chủ sau khi đăng nhập:"))
        self.bg_server = QButtonGroup()
        rb_row = QHBoxLayout()
        rb_row.setSpacing(12)
        self.rb_200  = QRadioButton("RDP-211.200")
        self.rb_12   = QRadioButton("Terminal-211.12")
        self.rb_none = QRadioButton("Chỉ đăng nhập")
        self.rb_200.setChecked(True)
        for rb in (self.rb_200, self.rb_12, self.rb_none):
            self.bg_server.addButton(rb)
            rb_row.addWidget(rb)
        rb_row.addStretch()
        layout.addLayout(rb_row)

        # --- Tự động đóng ---
        self.chk_auto_exit = QCheckBox("Tự động đóng sau khi đăng nhập thành công")
        self.chk_auto_exit.setChecked(True)
        layout.addWidget(self.chk_auto_exit)

        self.chk_block_browser = QCheckBox("Đóng tab callback GlobalProtect khi nó chiếm focus")
        self.chk_block_browser.setChecked(True)
        layout.addWidget(self.chk_block_browser)

        # --- Nút bấm ---
        btn_layout = QHBoxLayout()
        self.btn_run = QPushButton("TIẾN HÀNH ĐĂNG NHẬP")
        self.btn_run.setObjectName("run_button")
        self.btn_run.clicked.connect(self.start_automation)
        self.btn_cancel = QPushButton("HỦY")
        self.btn_cancel.setObjectName("btn_cancel")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.cancel_automation)
        btn_layout.addWidget(self.btn_run, 3)
        btn_layout.addWidget(self.btn_cancel, 1)
        layout.addLayout(btn_layout)

        # --- Logs ---
        layout.addWidget(QLabel("Nhật ký thực thi:"))
        self.txt_logs = QTextEdit()
        self.txt_logs.setObjectName("runtime_log")
        self.txt_logs.setReadOnly(True)
        layout.addWidget(self.txt_logs)

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _load_settings(self) -> None:
        if not os.path.exists(SETTINGS_FILE):
            return
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.txt_username.setText(data.get("username", ""))
            self.txt_capam_ip.setText(data.get("capam_ip", CAPAM_IP_DEFAULT))
            self.chk_auto_exit.setChecked(data.get("auto_exit", True))
            self.chk_block_browser.setChecked(data.get("block_browser", True))
        except Exception:
            pass

    def _save_settings(self) -> None:
        try:
            data = {
                "username": self.txt_username.text().strip(),
                "capam_ip": self.txt_capam_ip.text().strip(),
                "auto_exit": self.chk_auto_exit.isChecked(),
                "block_browser": self.chk_block_browser.isChecked(),
            }
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # UI Helpers
    # ------------------------------------------------------------------

    def activate_on_startup(self) -> None:
        """Bring tool forward once, unless automation already started."""
        if not self.worker or not self.worker.isRunning():
            clear_topmost(self)
            self.raise_()
            self.activateWindow()

    def _toggle_password(self) -> None:
        mode = QLineEdit.Normal if self.chk_show_pass.isChecked() else QLineEdit.Password
        self.txt_pass_prefix.setEchoMode(mode)

    def _log(self, text: str) -> None:
        self.txt_logs.append(text)

    def _set_controls_enabled(self, enabled: bool) -> None:
        for w in (
            self.txt_username, self.txt_pass_prefix, self.txt_capam_ip, self.txt_otp,
            self.rb_200, self.rb_12, self.rb_none,
            self.chk_show_pass, self.chk_auto_exit, self.chk_block_browser,
        ):
            w.setEnabled(enabled)
        self.btn_run.setEnabled(enabled)
        self.btn_cancel.setEnabled(not enabled)

    # ------------------------------------------------------------------
    # Automation Control
    # ------------------------------------------------------------------

    def start_automation(self) -> None:
        username = self.txt_username.text().strip()
        password_prefix = self.txt_pass_prefix.text().strip()
        otp = self.txt_otp.text().strip()
        capam_ip = self.txt_capam_ip.text().strip()

        if not username or not password_prefix:
            self._log("[!] Vui lòng nhập đầy đủ Tài khoản và Mật khẩu.")
            return
        if not capam_ip:
            self._log("[!] Vui lòng nhập IP máy chủ CAPAM.")
            self.txt_capam_ip.setFocus()
            return
        if len(otp) != 6 or not otp.isdigit():
            self._log("[!] Vui lòng nhập đúng mã OTP 6 số.")
            self.txt_otp.setFocus()
            return

        choice = "none"
        if self.rb_200.isChecked():
            choice = "200"
        elif self.rb_12.isChecked():
            choice = "12"

        self._set_controls_enabled(False)
        self._save_settings()
        self.txt_logs.clear()
        self._log("[INFO] Bắt đầu khởi chạy kịch bản tự động hóa...")

        self.worker = AutomationWorker(
            username,
            password_prefix,
            otp,
            choice,
            capam_ip,
            self.chk_block_browser.isChecked(),
        )
        self.worker.log_signal.connect(self._log)
        self.worker.finished_signal.connect(self._automation_finished)
        # Controller must not cover GP/CAPAM while guarded focus and clicks run.
        clear_topmost(self)
        self.showMinimized()
        self.worker.start()

    def cancel_automation(self) -> None:
        if self.worker and self.worker.isRunning():
            self._log("[!] Đang dừng kịch bản tự động hóa theo yêu cầu người dùng...")
            self.worker.requestInterruption()
            if not self.worker.wait(3000):
                self._log("[!] Đang chờ thao tác hệ thống hiện tại kết thúc an toàn...")
                return
            self._log("[!] Đã dừng thành công.")
        else:
            self._automation_finished(False)

    def _automation_finished(self, success: bool) -> None:
        if success and self.chk_auto_exit.isChecked():
            self._log("[INFO] Tự động đóng ứng dụng theo cài đặt...")
            QApplication.quit()
            return

        self._set_controls_enabled(True)
        self.txt_otp.clear()
        self.txt_otp.setFocus()
        clear_topmost(self)
        self.showNormal()
        self.raise_()
        self.activateWindow()
