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
        return False

    def get_window_rect(self, title_keyword: str, exact: bool = False) -> dict | None:
        """Lấy vị trí và kích thước của cửa sổ.

        Returns:
            Dict với keys 'x', 'y', 'w', 'h' hoặc None nếu không tìm thấy.
        """
        return None

    def take_screenshot(self, rect: dict, path: str) -> None:
        """Chụp ảnh vùng màn hình được chỉ định và lưu ra file."""
        pass

    def take_full_screenshot(self, path: str) -> None:
        """Chụp toàn màn hình và lưu ra file."""
        pass

    def kill_capam(self) -> None:
        """Tắt tiến trình CAPAM Client."""
        pass

    def launch_capam(self) -> bool:
        """Khởi động CAPAM Client. Returns True nếu thành công."""
        return False

    def launch_gp_ui(self) -> bool:
        """Kích hoạt hoặc hiển thị lại bảng UI của GlobalProtect.
        Returns True nếu thành công.
        """
        return False

    def get_gp_log_path(self) -> str:
        """Trả về đường dẫn tuyệt đối đến file log của GlobalProtect."""
        return ""
