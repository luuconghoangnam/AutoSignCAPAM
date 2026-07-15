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
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from config import CAPAM_IP_DEFAULT
from core.state_machine import AutomationWorker

SETTINGS_FILE = os.path.expanduser("~/.capam_autosign_settings.json")

_STYLESHEET = """
    QMainWindow { background-color: #1e1e2e; }
    QLabel { color: #cdd6f4; font-size: 12px; font-weight: bold; }
    QLineEdit {
        background-color: #313244; color: #89b4fa;
        border: 2px solid #45475a; border-radius: 6px;
        padding: 4px 6px; font-size: 13px; font-weight: bold; min-height: 22px;
    }
    QLineEdit#otp_input { font-size: 22px; letter-spacing: 5px; min-height: 36px; }
    QLineEdit:focus { border: 2px solid #89b4fa; }
    QRadioButton { color: #cdd6f4; font-size: 12px; spacing: 6px; }
    QRadioButton::indicator { width: 14px; height: 14px; }
    QPushButton {
        background-color: #89b4fa; color: #1e1e2e;
        font-size: 13px; font-weight: bold; border-radius: 6px; padding: 7px;
    }
    QPushButton:hover { background-color: #b4befe; }
    QPushButton:disabled { background-color: #45475a; color: #a6adc8; }
    QPushButton#btn_cancel { background-color: #f38ba8; color: #1e1e2e; }
    QPushButton#btn_cancel:hover { background-color: #eba0ac; }
    QPushButton#btn_cancel:disabled { background-color: #45475a; color: #a6adc8; }
    QCheckBox { color: #a6adc8; font-size: 12px; }
    QTextEdit {
        background-color: #11111b; color: #a6e3a1;
        border: 1px solid #45475a; border-radius: 4px;
        font-family: 'Monospace'; font-size: 11px;
    }
"""


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.worker: AutomationWorker | None = None
        self._init_ui()
        self._load_settings()

    # ------------------------------------------------------------------
    # UI Initialization
    # ------------------------------------------------------------------

    def _init_ui(self) -> None:
        self.setWindowTitle("CAPAM Auto-Sign In Tool")
        self.setFixedSize(480, 530)
        self.setStyleSheet(_STYLESHEET)

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
        self.txt_pass_prefix.setEchoMode(QLineEdit.Password)
        self.txt_pass_prefix.setPlaceholderText("mật khẩu")
        v_pass.addWidget(self.txt_pass_prefix)

        v_ip = QVBoxLayout()
        v_ip.setSpacing(3)
        v_ip.addWidget(QLabel("IP CAPAM:"))
        self.txt_capam_ip = QLineEdit()
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

        # --- Nút bấm ---
        btn_layout = QHBoxLayout()
        self.btn_run = QPushButton("TIẾN HÀNH ĐĂNG NHẬP")
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
            self.txt_pass_prefix.setText(data.get("password_prefix", ""))
            self.txt_capam_ip.setText(data.get("capam_ip", CAPAM_IP_DEFAULT))
            self.chk_auto_exit.setChecked(data.get("auto_exit", True))
        except Exception:
            pass

    def _save_settings(self) -> None:
        try:
            data = {
                "username": self.txt_username.text().strip(),
                "password_prefix": self.txt_pass_prefix.text().strip(),
                "capam_ip": self.txt_capam_ip.text().strip(),
                "auto_exit": self.chk_auto_exit.isChecked(),
            }
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # UI Helpers
    # ------------------------------------------------------------------

    def _toggle_password(self) -> None:
        mode = QLineEdit.Normal if self.chk_show_pass.isChecked() else QLineEdit.Password
        self.txt_pass_prefix.setEchoMode(mode)

    def _log(self, text: str) -> None:
        self.txt_logs.append(text)

    def _set_controls_enabled(self, enabled: bool) -> None:
        for w in (
            self.txt_username, self.txt_pass_prefix, self.txt_capam_ip, self.txt_otp,
            self.rb_200, self.rb_12, self.rb_none,
            self.chk_show_pass, self.chk_auto_exit,
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

        # Thu nhỏ cửa sổ UI để không che khuất CAPAM/GP khi chụp màn hình
        self.showMinimized()

        self.worker = AutomationWorker(username, password_prefix, otp, choice, capam_ip)
        self.worker.log_signal.connect(self._log)
        self.worker.finished_signal.connect(self._automation_finished)
        self.worker.start()

    def cancel_automation(self) -> None:
        if self.worker and self.worker.isRunning():
            self._log("[!] Đang dừng kịch bản tự động hóa theo yêu cầu người dùng...")
            self.worker.terminate()
            self.worker.wait()
            self._log("[!] Đã dừng thành công.")
        self._automation_finished(False)

    def _automation_finished(self, success: bool) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

        if success and self.chk_auto_exit.isChecked():
            self._log("[INFO] Tự động đóng ứng dụng theo cài đặt...")
            QApplication.quit()
            return

        self._set_controls_enabled(True)
        self.txt_otp.clear()
        self.txt_otp.setFocus()
