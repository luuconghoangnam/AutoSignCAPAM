"""
adapters/__init__.py — Factory để lấy adapter phù hợp với HĐH hiện tại
"""
import platform


def get_os_adapter():
    """Trả về OSAdapter phù hợp với hệ điều hành đang chạy."""
    if platform.system() == "Windows":
        from adapters.windows import WindowsAdapter
        return WindowsAdapter()
    from adapters.linux import LinuxAdapter
    return LinuxAdapter()
