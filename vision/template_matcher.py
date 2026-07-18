"""
vision/template_matcher.py — Tìm và click nút RDP trong danh sách CAPAM
"""
import os
from functools import lru_cache

import cv2
import numpy as np

from config import get_resource_path


# Calibrated from real CAPAM captures at Windows 100%, 125%, and 150%.
# Java renders the "12" row slightly smaller than nominal Windows DPI.
_CALIBRATED_SCALES = [1.0, 0.95, 1.25, 1.15, 1.5, 1.4]


@lru_cache(maxsize=8)
def _load_template(path: str, modified_ns: int) -> np.ndarray | None:
    """Cache grayscale template; mtime in key invalidates changed assets."""
    image = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    return image


def _get_template(path: str) -> np.ndarray | None:
    try:
        modified_ns = os.stat(path).st_mtime_ns
    except OSError:
        return None
    return _load_template(path, modified_ns)


def _scaled_templates(
    template: np.ndarray,
    scene_shape: tuple,
    scales: list[float] | None = None,
) -> list[tuple[float, np.ndarray]]:
    """Generate practical UI scales for 100%, 125%, 150% DPI/window zoom."""
    scene_h, scene_w = scene_shape[:2]
    variants = []
    if scales is None:
        fallback = list(np.arange(0.5, 2.01, 0.1).round(2))
        scales = _CALIBRATED_SCALES + [
            scale for scale in fallback if scale not in _CALIBRATED_SCALES
        ]
    for scale in scales:
        width = max(1, round(template.shape[1] * scale))
        height = max(1, round(template.shape[0] * scale))
        if width > scene_w or height > scene_h:
            continue
        # Linear matches Windows/Java UI scaling more consistently than cubic.
        interpolation = cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR
        variants.append((scale, cv2.resize(template, (width, height), interpolation=interpolation)))
    return variants


def _best_match(scene: np.ndarray, template: np.ndarray):
    """Find global best scale; never stop at first merely acceptable match."""
    best = None
    for scale, variant in _scaled_templates(template, scene.shape):
        result = cv2.matchTemplate(scene, variant, cv2.TM_CCOEFF_NORMED)
        _, score, _, location = cv2.minMaxLoc(result)
        if best is None or score > best[0]:
            best = (score, location, variant.shape[:2], scale)
    if best is None:
        return best

    # Coarse 10% scan can miss Java UI scaling such as 95% or 145%.
    coarse_scale = best[3]
    fine_scales = [
        round(scale, 2)
        for scale in np.arange(max(0.5, coarse_scale - 0.1),
                               min(2.0, coarse_scale + 0.1) + 0.001, 0.05)
        if abs(scale - coarse_scale) > 0.001
    ]
    for scale, variant in _scaled_templates(template, scene.shape, fine_scales):
        result = cv2.matchTemplate(scene, variant, cv2.TM_CCOEFF_NORMED)
        _, score, _, location = cv2.minMaxLoc(result)
        if score > best[0]:
            best = (score, location, variant.shape[:2], scale)
    return best


def find_device_rdp_button(
    scene: np.ndarray,
    device_choice: str,
    log_fn=None,
    return_details: bool = False,
) -> tuple[int, int] | dict | None:
    """Tìm nút RDP tương ứng với thiết bị được chọn trong ảnh chụp màn hình.

    Args:
        scene: Ảnh chụp màn hình toàn màn hình dạng numpy array (BGR).
        device_choice: '200' hoặc '12' — xác định template ảnh thiết bị cần tìm.
        log_fn: Hàm callback để ghi log (tùy chọn).

    Returns:
        Tuple (click_x, click_y) tọa độ trung tâm nút RDP phù hợp, hoặc None.
    """

    def _log(msg):
        if log_fn:
            log_fn(msg)

    dev_template_name = f"template_{device_choice}.png"
    dev_template_path = get_resource_path(dev_template_name)
    rdp_template_path = get_resource_path("template_rdp.png")

    dev_template = _get_template(dev_template_path)
    rdp_template = _get_template(rdp_template_path)

    if scene is None or dev_template is None or rdp_template is None:
        _log(f"Không thể tải ảnh template cần thiết (Choice: {device_choice}).")
        return None
    scene_h, scene_w = scene.shape[:2]
    gray_scene = cv2.cvtColor(scene, cv2.COLOR_BGR2GRAY)
    gray_dev_template = dev_template
    gray_rdp_template = rdp_template
    _log(f"Đang tìm nhãn thiết bị '{dev_template_name}' trên màn hình...")
    dev_match = _best_match(gray_scene, gray_dev_template)
    if dev_match is None:
        return None
    max_val_dev, max_loc_dev, dev_shape, matched_scale = dev_match

    if max_val_dev < 0.65:
        _log(f"Không tìm thấy nhãn thiết bị {device_choice} (Độ khớp: {max_val_dev:.2f}).")
        return None

    dev_x, dev_y = max_loc_dev
    dev_h, dev_w = dev_shape
    dev_center_y = dev_y + dev_h / 2
    _log(f"Đã tìm thấy thiết bị '{device_choice}' tại Y={dev_center_y:.1f}. Đang quét nút RDP...")

    # Device and RDP controls share DPI. Search only matching row and nearby scales.
    # Crop must contain full RDP button even when DPI makes it taller than row gap.
    row_margin = max(
        35,
        round(scene_h * 0.06),
        round(rdp_template.shape[0] * matched_scale + 10),
    )
    row_top = max(0, round(dev_center_y - row_margin))
    row_bottom = min(scene_h, round(dev_center_y + row_margin))
    row_scene = gray_scene[row_top:row_bottom, :]
    nearby_scales = sorted({
        round(scale, 2)
        for scale in np.arange(max(0.5, matched_scale - 0.1),
                               min(2.0, matched_scale + 0.1) + 0.001, 0.05)
    })
    best_rdp = None
    min_dist_y = float("inf")
    best_score = 0.65
    for _, variant in _scaled_templates(gray_rdp_template, row_scene.shape, nearby_scales):
        result = cv2.matchTemplate(row_scene, variant, cv2.TM_CCOEFF_NORMED)
        _, score, _, location = cv2.minMaxLoc(result)
        if score < best_score:
            continue
        pt = (location[0], location[1] + row_top)
        shape = variant.shape[:2]
        rdp_center_y = pt[1] + shape[0] / 2
        dist_y = abs(rdp_center_y - dev_center_y)
        if dist_y < row_margin:
            best_score = score
            min_dist_y = dist_y
            best_rdp = (pt, shape)

    if not best_rdp:
        _log("Không tìm thấy nút RDP cùng dòng với thiết bị đã chọn.")
        return None

    pt, shape = best_rdp
    rdp_h, rdp_w = shape
    click_x = int(pt[0] + rdp_w / 2)
    click_y = int(pt[1] + rdp_h / 2)
    _log(f"Xác định nút RDP tại ({click_x}, {click_y}) — cách dòng thiết bị {min_dist_y:.1f}px.")
    if return_details:
        return {
            "point": (click_x, click_y),
            "device_score": float(max_val_dev),
            "rdp_score": float(best_score),
            "scale": float(matched_scale),
        }
    return click_x, click_y
