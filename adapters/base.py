"""
adapters/base.py — Abstract base class cho OS adapters
"""


class OSAdapter:
    """Interface chuẩn để tương tác với hệ điều hành.
    Mỗi nền tảng (Linux, Windows) sẽ implement lớp này.
    """

    def focus_window(self, title_keyword: str, exact: bool = False) -> bool:
        """Đưa cửa sổ có tiêu đề khớp lên foreground và kích hoạt.

        Args:
            title_keyword: Tiêu đề cửa sổ cần tìm.
            exact: Nếu True, khớp toàn bộ tiêu đề; nếu False, khớp một phần.
        Returns:
            True nếu tìm và focus thành công.
        """
        raise NotImplementedError

    def focus_rect(self, rect: dict) -> bool:
        """Focus exact window instance represented by rect/HWND."""
        raise NotImplementedError

    def wait_focus_rect(self, rect: dict, timeout: float = 5.0) -> bool:
        """Retry exact target focus while transient windows finish opening."""
        return self.focus_rect(rect)

    def suppress_browser_foreground(self) -> bool:
        """Minimize browser only when it currently owns foreground."""
        return False

    def is_foreground(self, rect: dict) -> bool:
        """Return whether exact window instance currently owns foreground."""
        raise NotImplementedError

    def get_window_rect(self, title_keyword: str, exact: bool = False) -> dict | None:
        """Lấy vị trí và kích thước của cửa sổ.

        Returns:
            Dict với keys 'x', 'y', 'w', 'h' hoặc None nếu không tìm thấy.
        """
        raise NotImplementedError

    def get_capam_main_rect(self) -> dict | None:
        """Return main CAPAM window, excluding same-title dialogs."""
        return self.get_window_rect("Symantec Privileged Access Manager", exact=True)

    def get_capam_dialog_rect(self) -> dict | None:
        """Return same-title CAPAM child dialog, excluding main window."""
        return self.get_window_rect("Symantec Privileged Access Manager", exact=True)

    def get_window_rect_for_hwnd(self, hwnd) -> dict | None:
        """Return current rect for exact window instance."""
        return None

    def take_screenshot(self, rect: dict, path: str) -> None:
        """Chụp ảnh vùng màn hình được chỉ định và lưu ra file."""
        raise NotImplementedError

    def capture_window(self, rect: dict):
        """Capture exact window into memory; returns BGR ndarray or None."""
        return None

    def take_full_screenshot(self, path: str) -> None:
        """Chụp toàn màn hình và lưu ra file."""
        raise NotImplementedError

    def refresh_window(self, rect: dict) -> None:
        """Yêu cầu cửa sổ vẽ lại nội dung trước khi chụp."""
        return None

    def kill_capam(self) -> None:
        """Tắt tiến trình CAPAM Client."""
        raise NotImplementedError

    def kill_window_process(self, rect: dict) -> bool:
        """Tắt process sở hữu HWND trong rect."""
        raise NotImplementedError

    def launch_capam(self) -> bool:
        """Khởi động CAPAM Client. Returns True nếu thành công."""
        raise NotImplementedError

    def launch_gp_ui(self) -> bool:
        """Kích hoạt hoặc hiển thị lại bảng UI của GlobalProtect.
        Returns True nếu thành công.
        """
        return False

    def get_gp_log_path(self) -> str:
        """Trả về đường dẫn tuyệt đối đến file log của GlobalProtect."""
        raise NotImplementedError

    def get_rdp_windows(self) -> dict[int, str]:
        """Return visible mstsc window handles and titles in current session."""
        return {}

    def window_belongs_to_process(self, hwnd: int, process_name: str) -> bool:
        """Return whether exact HWND is currently owned by expected process."""
        return False
