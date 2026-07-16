"""
vision/field_detector.py — Nhận diện các ô nhập liệu bằng OpenCV

Thay thế 2 hàm detect_gp_fields / detect_capam_fields bằng một hàm
thống nhất với "profile" xác định ngưỡng kích thước khác nhau.
Có thêm fallback pixel-based khi Canny không tìm được contour.
"""
import os
import platform
import cv2
import numpy as np


# --- Legacy pixel limits retained as broad safety limits. Main limits use ratios. ---
_PROFILES = {
    "gp": {
        "min_w": (100, 120),   # (Windows, Linux)
        "max_w": (320, 290),
        "min_h": (10, 15),
        "max_h": (55, 45),
        "min_mean": (150, 200),  # độ sáng trung bình tối thiểu (lọc nút bấm)
    },
    "capam": {
        "min_w": (60, 80),
        "max_w": (320, 280),
        "min_h": (10, 12),
        "max_h": (50, 40),
        "min_mean": (180, 180),    # Lọc nút bấm xanh/xám tối
    },
    "windows_security": {
        "min_w": (60, 80),
        "max_w": (380, 320),
        "min_h": (10, 12),
        "max_h": (50, 40),
        "min_mean": (0, 0),
    },
}

_IS_WINDOWS = platform.system() == "Windows"


def detect_input_fields(
    screenshot_path: str,
    profile: str = "capam",
    debug_output_path: str | None = None,
) -> list[tuple[int, int, int, int]]:
    """Phát hiện các ô nhập liệu trong ảnh chụp màn hình.

    Args:
        screenshot_path: Đường dẫn đến file ảnh chụp màn hình.
        profile: Tên profile xác định ngưỡng kích thước ('gp', 'capam', 'windows_security').
        debug_output_path: Nếu cung cấp, lưu ảnh debug có vẽ khung các ô nhận diện được.

    Returns:
        Danh sách (x, y, w, h) của các ô nhập liệu, đã sắp xếp từ trên xuống dưới.
    """
    img = cv2.imread(screenshot_path)
    if img is None:
        return []

    cfg = _PROFILES.get(profile, _PROFILES["capam"])
    idx = 0 if _IS_WINDOWS else 1
    min_mean = cfg["min_mean"][idx]
    image_h, image_w = img.shape[:2]
    # Controls scale with DPI. Absolute pixel thresholds reject 125%/150% frames.
    ratio_limits = {
        "gp": (0.25, 0.9, 0.015, 0.18),
        "capam": (0.08, 0.85, 0.008, 0.18),
        "windows_security": (0.08, 0.9, 0.008, 0.18),
    }
    min_wr, max_wr, min_hr, max_hr = ratio_limits.get(profile, ratio_limits["capam"])

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(blurred, 50, 150)
    # Dùng RETR_LIST thay vì RETR_EXTERNAL để phát hiện các ô nhập liệu bên trong đường viền/khung cửa sổ (light theme/Windows 11)
    contours, _ = cv2.findContours(edged.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    debug_img = img.copy() if debug_output_path else None
    fields = []

    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if debug_img is not None:
            cv2.rectangle(debug_img, (x, y), (x + w, y + h), (0, 0, 255), 1)
            cv2.putText(debug_img, f"{w}x{h}", (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 0, 255), 1)

        if min_wr <= w / image_w <= max_wr and min_hr <= h / image_h <= max_hr:
            if min_mean > 0:
                crop = gray[y:y+h, x:x+w]
                if np.mean(crop) < min_mean:
                    continue
            fields.append((x, y, w, h))
            if debug_img is not None:
                cv2.rectangle(debug_img, (x, y), (x + w, y + h), (0, 255, 0), 2)

    # Nếu không tìm được qua Canny, thử pixel-based: tìm vùng màu sáng hình chữ nhật
    if not fields and profile == "gp":
        fields = _pixel_fallback(gray, min_wr, max_wr, min_hr, max_hr, debug_img)

    # Loại bỏ các ô nhập trùng lặp hoặc lồng nhau (viền trong / viền ngoài của cùng 1 ô)
    fields = _deduplicate_fields(fields)

    if debug_img is not None and debug_output_path:
        cv2.imwrite(debug_output_path, debug_img)

    return sorted(fields, key=lambda f: (f[1], f[0]))


def _deduplicate_fields(fields: list[tuple[int, int, int, int]], threshold: int = 10) -> list[tuple[int, int, int, int]]:
    """Loại bỏ các ô nhập trùng lặp hoặc lồng nhau (chỉ giữ lại ô có viền ngoài to hơn)."""
    # Sắp xếp diện tích từ lớn đến bé để xử lý ô to/ngoài trước
    sorted_by_area = sorted(fields, key=lambda f: f[2] * f[3], reverse=True)
    kept = []
    for f in sorted_by_area:
        x, y, w, h = f
        is_duplicate = False
        for k in kept:
            kx, ky, kw, kh = k
            # Nếu tọa độ x, y của ô đang xét quá gần với ô đã giữ lại, coi như cùng 1 ô
            if abs(x - kx) < threshold and abs(y - ky) < threshold:
                is_duplicate = True
                break
        if not is_duplicate:
            kept.append(f)
    return kept


def _pixel_fallback(
    gray: np.ndarray,
    min_wr: float, max_wr: float,
    min_hr: float, max_hr: float,
    debug_img: np.ndarray | None,
) -> list[tuple[int, int, int, int]]:
    """Fallback: Tìm vùng sáng hình chữ nhật trong ảnh xám.
    Dùng khi Canny bỏ sót các ô nhập có viền mờ nhạt (flat design của GP trên Windows).
    """
    # Ngưỡng: tìm vùng sáng (màu nền ô nhập liệu thường > 230 trên GP Windows)
    _, thresh = cv2.threshold(gray, 220, 255, cv2.THRESH_BINARY)
    # Dùng RETR_LIST để lấy cả các ô nhập liệu nằm lồng bên trong nền trắng của cửa sổ
    contours, _ = cv2.findContours(thresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    fields = []
    image_h, image_w = gray.shape[:2]
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if min_wr <= w / image_w <= max_wr and min_hr <= h / image_h <= max_hr:
            fields.append((x, y, w, h))
            if debug_img is not None:
                cv2.rectangle(debug_img, (x, y), (x + w, y + h), (255, 165, 0), 2)
    return fields
