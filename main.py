"""
main.py — Entry point của ứng dụng AutoSignCAPAM

Chỉ chứa logic khởi tạo tối thiểu: DPI setup, QApplication, MainWindow, exec_().
Toàn bộ logic tự động hóa nằm trong các module core/, adapters/, vision/, ui/.
"""
import sys
# config.py tự setup DPI awareness khi import
import config  # noqa: F401 — side-effect import

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont

from ui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))

    window = MainWindow()
    window.show()
    window.raise_()
    window.activateWindow()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
