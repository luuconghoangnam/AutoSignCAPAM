"""
adapters/__init__.py — Factory để lấy adapter phù hợp với HĐH hiện tại
"""
import platform


def get_os_adapter():
    """Trả về OSAdapter phù hợp với hệ điều hành đang chạy."""
    system = platform.system()
    if system == "Windows":
        from adapters.windows import WindowsAdapter
        return WindowsAdapter()
    if system == "Linux":
        from adapters.linux import LinuxAdapter
        return LinuxAdapter()
    raise RuntimeError(f"Unsupported operating system: {system}")
