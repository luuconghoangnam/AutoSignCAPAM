"""
core/rdp_handler.py — Click nút RDP và điền thông tin vào bảng Windows Security
"""
import os
import tempfile
import time
import uuid

import cv2
import pyautogui

from adapters.base import OSAdapter
from capture.frame import FrameSnapshot
from capture.window_capture import FrameCapture
from recognition.geometry import points_stable, to_screen_point
from vision.template_matcher import find_device_rdp_button
from config import write_text_safely


WIN_SEC_TITLE = "Symantec Privileged Access Manager"
WIN_SEC_TITLES = (WIN_SEC_TITLE, "Windows Security")
_POLL_INTERVAL = 0.5


class RDPHandler:
    """Xử lý luồng click RDP và điền thông tin Windows Security."""

    def __init__(self, adapter: OSAdapter, log_fn=None, cancel_fn=None):
        self.adapter = adapter
        self._log = log_fn or (lambda msg: None)
        self._cancelled = cancel_fn or (lambda: False)
        self._capture = FrameCapture(adapter)
        self._attempt_context = None
        run_id = f"{os.getpid()}_{uuid.uuid4().hex}"
        self._screenshot_tmp = os.path.join(tempfile.gettempdir(), f"capam_window_{run_id}.png")

    @staticmethod
    def _wait_next_poll(poll_started: float, deadline: float) -> None:
        remaining = min(deadline, poll_started + _POLL_INTERVAL) - time.monotonic()
        if remaining > 0:
            time.sleep(remaining)

    @staticmethod
    def _postcondition_poll_delay(attempt: int) -> float:
        """Probe new dialogs quickly, then back off to avoid event/log spam."""
        return min(0.75, 0.1 * (1.5 ** attempt))

    @staticmethod
    def _same_rect(previous: dict | None, current: dict) -> bool:
        if not previous:
            return False
        return all(previous.get(key) == current.get(key) for key in ("id", "x", "y", "w", "h"))

    def _click_started_rdp(self, context: dict, expected_session_title: str | None) -> bool:
        existing_auth_hwnds = context["auth_hwnds"]
        for title in WIN_SEC_TITLES:
            candidates = (
                [self.adapter.get_capam_dialog_rect()]
                if title == WIN_SEC_TITLE
                else self.adapter.get_window_rects(title, exact=True)
            )
            if any(item and item.get("id") not in existing_auth_hwnds for item in candidates):
                return True
        if set(self.adapter.get_rdp_windows()) - set(context["rdp_windows"]):
            return True
        if expected_session_title:
            session = self.adapter.get_window_rect(expected_session_title, exact=True)
            previous = context.get("session")
            if session and (not previous or session.get("id") != previous.get("id")):
                return True
        return False

    def wait_for_device_list(self, capam_ip: str, max_wait: int = 60) -> dict | None:
        """Chờ cửa sổ danh sách thiết bị CAPAM xuất hiện.
        Returns: rect dict hoặc None nếu timeout.
        """
        target_title = f"Symantec Privileged Access Manager Client - {capam_ip}"
        started = time.monotonic()
        deadline = started + max_wait
        while time.monotonic() < deadline:
            if self._cancelled():
                return None
            poll_started = time.monotonic()
            rect = self.adapter.get_window_rect(target_title, exact=True)
            if rect:
                elapsed = time.monotonic() - started
                self._log(f"Đã phát hiện danh sách thiết bị sau {elapsed:.1f} giây.")
                return rect
            self._wait_next_poll(poll_started, deadline)
        self._log("Quá thời gian chờ danh sách thiết bị CAPAM.")
        return None

    def click_rdp(
        self,
        device_choice: str,
        capam_ip: str,
        max_wait: int = 60,
        expected_rect: dict | None = None,
    ) -> bool:
        """Chụp cửa sổ CAPAM, tìm và click nút RDP cho thiết bị được chọn.
        Kiểm tra mỗi 0.5 giây trong tối đa max_wait giây.
        Returns: True nếu click thành công.
        """
        target_title = f"Symantec Privileged Access Manager Client - {capam_ip}"
        started = time.monotonic()
        deadline = started + max_wait
        previous_result = None
        previous_rect = None
        stable_count = 0
        next_detail_log = started
        focused_once = False
        rendered_at = None
        match_misses = 0
        previous_snapshot = None
        while time.monotonic() < deadline:
            if self._cancelled():
                return False
            poll_started = time.monotonic()
            elapsed = time.monotonic() - started
            verbose = poll_started >= next_detail_log
            if verbose:
                self._log(f"Đang tìm nút RDP... ({elapsed:.1f}/{max_wait}s)")
                next_detail_log = poll_started + 2
            rect = (
                self.adapter.get_window_rect_for_hwnd(expected_rect.get("id"))
                if expected_rect else self.adapter.get_window_rect(target_title, exact=True)
            )
            if not rect:
                self._wait_next_poll(poll_started, deadline)
                continue
            if expected_rect and rect.get("id") != expected_rect.get("id"):
                self._log("Instance danh sách thiết bị CAPAM đã thay đổi; hủy click RDP.")
                return False

            # Java HWND capture can be blank while occluded. Activate exact device-list
            # window before the first capture, not after successful recognition.
            if not focused_once or not self.adapter.is_foreground(rect):
                self.adapter.suppress_browser_foreground()
                if not self.adapter.wait_focus_rect(rect, timeout=5.0):
                    self._log("Không thể đưa danh sách thiết bị CAPAM lên foreground để nhận diện.")
                    self._wait_next_poll(poll_started, deadline)
                    continue
                self.adapter.refresh_window(rect)
                time.sleep(0.25)
                focused_once = True
            snapshot = self._capture.capture(rect)
            scene = snapshot.image if snapshot else None
            if scene is None:
                try:
                    self.adapter.take_screenshot(rect, self._screenshot_tmp)
                    scene = cv2.imread(self._screenshot_tmp)
                except Exception as e:
                    self._log(f"Lỗi chụp màn hình: {e}")
                finally:
                    try:
                        os.remove(self._screenshot_tmp)
                    except Exception:
                        pass

            if scene is None:
                self._log("Không thể đọc ảnh cửa sổ CAPAM vừa chụp.")
                self._wait_next_poll(poll_started, deadline)
                continue

            snapshot = snapshot or FrameSnapshot.from_image(scene, rect)
            if snapshot.is_blank:
                self._log("Ảnh CAPAM chưa render hoặc đang bị che; yêu cầu vẽ lại...")
                self.adapter.refresh_window(rect)
                focused_once = False
                self._wait_next_poll(poll_started, deadline)
                continue

            frame_delta = snapshot.mean_delta(previous_snapshot)
            previous_snapshot = snapshot
            if frame_delta > 18.0:
                self._log("CAPAM đang cập nhật danh sách; chờ frame ổn định...")
                self._wait_next_poll(poll_started, deadline)
                continue

            if rendered_at is None:
                rendered_at = time.monotonic()
            elif time.monotonic() - rendered_at >= 20:
                self._log(
                    "Màn hình danh sách đã render nhưng không nhận diện được thiết bị "
                    "sau 20 giây; dừng retry để tránh vòng lặp kéo dài."
                )
                return False

            result = find_device_rdp_button(
                scene,
                device_choice,
                log_fn=self._log if verbose else None,
                return_details=True,
            )
            if result and (
                result["device_score"] < 0.70 or result["rdp_score"] < 0.70
            ):
                self._log(
                    f"Ứng viên chưa đủ tin cậy (device={result['device_score']:.2f}, "
                    f"rdp={result['rdp_score']:.2f}); chờ frame mới."
                )
                result = None
            if result:
                point = result["point"]
                match_misses = 0
                unchanged = (
                    self._same_rect(previous_rect, rect)
                    and points_stable(
                        previous_result,
                        point,
                        scene.shape[1],
                        scene.shape[0],
                    )
                )
                stable_count = stable_count + 1 if unchanged else 1
                previous_result = point
                previous_rect = rect.copy()
                if stable_count < 2:
                    self._wait_next_poll(poll_started, deadline)
                    continue
                current_rect = self.adapter.get_window_rect_for_hwnd(rect.get("id"))
                if not self._same_rect(rect, current_rect or {}):
                    stable_count = 0
                    previous_result = None
                    previous_rect = None
                    continue
                if not self.adapter.focus_rect(rect):
                    stable_count = 0
                    continue
                current_rect = self.adapter.get_window_rect_for_hwnd(rect.get("id"))
                if not self._same_rect(rect, current_rect or {}):
                    stable_count = 0
                    previous_result = None
                    previous_rect = None
                    continue
                click_x, click_y = to_screen_point(
                    point,
                    scene.shape[1],
                    scene.shape[0],
                    snapshot.rect,
                )
                self._log(f"Đang click nút RDP tại ({click_x}, {click_y})...")
                if not self.adapter.is_foreground(rect):
                    self._log("Foreground đổi trước click RDP; hủy click.")
                    stable_count = 0
                    continue
                expected_session_title = {
                    "200": "RDP-211.200",
                    "12": "Terminal-211.12",
                }.get(device_choice)
                self._attempt_context = {
                    "clicked_at": time.monotonic(),
                    "device_list": rect.copy(),
                    "auth_hwnds": {
                        item["id"]
                        for title in WIN_SEC_TITLES
                        for item in self.adapter.get_window_rects(title, exact=True)
                    },
                    "rdp_windows": self.adapter.get_rdp_windows(),
                    "session": (
                        self.adapter.get_window_rect(expected_session_title, exact=True)
                        if expected_session_title else None
                    ),
                }
                # CAPAM is Java Swing, so use a physical click. Adapter temporarily
                # raises exact HWND and verifies WindowFromPoint before clicking.
                if not self.adapter.click_visible_window_point(rect, click_x, click_y):
                    self._log(
                        "Không thể đưa CAPAM lên trên hoặc điểm RDP vẫn bị cửa sổ khác che; "
                        "không gửi click."
                    )
                    stable_count = 0
                    previous_result = None
                    previous_rect = None
                    self._attempt_context = None
                    rendered_at = time.monotonic()
                    self._wait_next_poll(poll_started, deadline)
                    continue
                self._log("Đã gửi click chuột thật vào nút RDP.")
                # Opening an RDP session is not idempotent. CAPAM may need several
                # seconds to create its auth dialog, so never click this row twice.
                confirm_deadline = min(deadline, time.monotonic() + 15.0)
                confirm_attempt = 0
                while time.monotonic() < confirm_deadline:
                    if self._cancelled():
                        return False
                    self.adapter.suppress_browser_foreground()
                    if self._click_started_rdp(self._attempt_context, expected_session_title):
                        return True
                    remaining = confirm_deadline - time.monotonic()
                    if remaining > 0:
                        time.sleep(min(remaining, self._postcondition_poll_delay(confirm_attempt)))
                    confirm_attempt += 1
                self._log(
                    "Click RDP chưa tạo bảng xác thực hoặc phiên RDP sau 15 giây; "
                    "không click lại để tránh mở hai phiên."
                )
                return False
            match_misses += 1
            stable_count = 0
            previous_result = None
            previous_rect = None
            if match_misses % 4 == 0:
                self._log(
                    f"Nhận diện trượt {match_misses} frame; kích hoạt lại đúng cửa sổ CAPAM..."
                )
                focused_once = False
                self.adapter.suppress_browser_foreground()
                self.adapter.wait_focus_rect(rect, timeout=2.0)
                self.adapter.refresh_window(rect)
            elif match_misses % 2 == 0:
                self._log(f"Nhận diện trượt {match_misses} frame; yêu cầu CAPAM vẽ lại...")
                self.adapter.refresh_window(rect)
            self._wait_next_poll(poll_started, deadline)
        return False

    def fill_windows_security(self, username: str, password: str, device_choice: str) -> bool:
        """Chờ và điền thông tin đăng nhập vào bảng Windows Security.
        Returns: True nếu hoàn tất.
        """
        self._log("Đang chờ bảng Windows Security xuất hiện...")
        context = self._attempt_context or {}
        existing_rdp_windows = context.get("rdp_windows", self.adapter.get_rdp_windows())
        existing_auth_hwnds = context.get("auth_hwnds", set())
        expected_session_title = {
            "200": "RDP-211.200",
            "12": "Terminal-211.12",
        }.get(device_choice)
        existing_session = context.get("session") or (
            self.adapter.get_window_rect(expected_session_title, exact=True)
            if expected_session_title else None
        )
        rect = None
        window_title = None
        started = time.monotonic()
        deadline = started + 30
        while time.monotonic() < deadline:
            if self._cancelled():
                return False
            candidates = []
            for candidate_title in WIN_SEC_TITLES:
                if candidate_title == WIN_SEC_TITLE:
                    candidate = self.adapter.get_capam_dialog_rect()
                    title_candidates = [candidate] if candidate else []
                else:
                    title_candidates = self.adapter.get_window_rects(candidate_title, exact=True)
                for candidate in title_candidates:
                    if not candidate or candidate.get("id") in existing_auth_hwnds:
                        continue
                    if candidate.get("process_name", "").lower() != "capamclient.exe":
                        continue
                    candidates.append((candidate_title, candidate))
            unique = {candidate["id"]: (title, candidate) for title, candidate in candidates}
            if len(unique) == 1:
                window_title, rect = next(iter(unique.values()))
                elapsed = time.monotonic() - started
                self._log(
                    f"Đã phát hiện bảng xác thực '{window_title}' sau {elapsed:.1f} giây."
                )
            elif len(unique) > 1:
                self._log("Có nhiều bảng xác thực mới; từ chối nhập credential do ambiguous.")
                return False
            if rect:
                break
            time.sleep(min(_POLL_INTERVAL, max(0, deadline - time.monotonic())))

        if not rect:
            self._log("Không tìm thấy bảng xác thực RDP CAPAM trong 30 giây.")
            return False

        # Credential provider does not expose child controls through UIA/JAB.
        # The real dialog starts with Username focused; one Tab reaches Password.
        if not self.adapter.wait_focus_rect(rect, timeout=5.0):
            self._log("Không thể đưa overlay xác thực lên foreground trước khi nhập.")
            return False
        current_rect = self.adapter.get_window_rect_for_hwnd(rect.get("id"))
        if not self._same_rect(rect, current_rect or {}):
            self._log("Bảng xác thực đã di chuyển hoặc thay đổi; dừng trước khi nhập.")
            return False

        pyautogui.hotkey("ctrl", "a")
        if not write_text_safely(username, lambda: self.adapter.is_foreground(rect)):
            return False
        self._log(f"Đã nhập Username Windows Security: {username}")

        if not self.adapter.is_foreground(rect):
            return False
        pyautogui.press("tab")
        time.sleep(0.15)
        if not self.adapter.is_foreground(rect):
            self._log("Foreground đổi sau Tab Windows Security; dừng nhập Password.")
            return False
        pyautogui.hotkey("ctrl", "a")
        if not write_text_safely(password, lambda: self.adapter.is_foreground(rect)):
            return False
        self._log("Đã nhập Password Windows Security.")

        if not self.adapter.is_foreground(rect):
            self._log("Foreground đổi; không gửi Enter Windows Security.")
            return False
        submitted_hwnd = rect.get("id")
        pyautogui.press("enter")
        self._log("Đã gửi Windows Security; đang xác minh kết quả...")

        deadline = time.monotonic() + 15
        closed_at = None
        while time.monotonic() < deadline:
            if self._cancelled():
                return False
            if not self.adapter.get_window_rect_for_hwnd(submitted_hwnd):
                closed_at = closed_at or time.monotonic()
                # Reject an immediate replacement credential dialog (auth retry).
                replacement = None
                for candidate_title in WIN_SEC_TITLES:
                    replacement = (
                        self.adapter.get_capam_dialog_rect()
                        if candidate_title == WIN_SEC_TITLE
                        else self.adapter.get_window_rect(candidate_title, exact=True)
                    )
                    if replacement:
                        break
                current_rdp_windows = self.adapter.get_rdp_windows()
                new_rdp_windows = set(current_rdp_windows) - set(existing_rdp_windows)
                changed_rdp_windows = {
                    hwnd for hwnd, title in current_rdp_windows.items()
                    if hwnd in existing_rdp_windows and title != existing_rdp_windows[hwnd]
                }
                current_session = (
                    self.adapter.get_window_rect(expected_session_title, exact=True)
                    if expected_session_title else None
                )
                capam_session_ready = bool(
                    current_session
                    and self.adapter.window_belongs_to_process(
                        current_session.get("id"), "CAPAMClient.exe"
                    )
                    and (
                        not existing_session
                        or current_session.get("id") != existing_session.get("id")
                    )
                )
                if not replacement and capam_session_ready:
                    self._log(
                        f"Windows Security đã đóng và phiên '{expected_session_title}' đã xuất hiện."
                    )
                    return True
                if not replacement and (new_rdp_windows or changed_rdp_windows):
                    self._log("Windows Security đã đóng và cửa sổ RDP đã chuyển trạng thái.")
                    return True
                if replacement and replacement.get("id") != submitted_hwnd:
                    self._log("Windows Security xuất hiện lại; thông tin xác thực có thể bị từ chối.")
                    return False
            time.sleep(0.2)

        self._log(
            f"Không thấy phiên '{expected_session_title}' hoặc cửa sổ RDP mới sau 15 giây; "
            "không xác nhận kết nối thành công."
        )
        return False
