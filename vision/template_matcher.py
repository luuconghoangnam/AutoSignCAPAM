"""
vision/template_matcher.py — Tìm và click nút RDP trong danh sách CAPAM
"""
import os
import gc
import cv2
import numpy as np

from config import get_resource_path


def find_device_rdp_button(
    scene: np.ndarray,
    device_choice: str,
    log_fn=None,
) -> tuple[int, int] | None:
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

    dev_template = cv2.imread(dev_template_path)
    rdp_template = cv2.imread(rdp_template_path)

    if scene is None or dev_template is None or rdp_template is None:
        _log(f"Không thể tải ảnh template cần thiết (Choice: {device_choice}).")
        return None

    _log(f"Đang tìm nhãn thiết bị '{dev_template_name}' trên màn hình...")
    res_dev = cv2.matchTemplate(scene, dev_template, cv2.TM_CCOEFF_NORMED)
    _, max_val_dev, _, max_loc_dev = cv2.minMaxLoc(res_dev)

    if max_val_dev < 0.65:
        _log(f"Không tìm thấy nhãn thiết bị {device_choice} (Độ khớp: {max_val_dev:.2f}).")
        del dev_template, rdp_template, res_dev
        gc.collect()
        return None

    dev_x, dev_y = max_loc_dev
    dev_h, dev_w = dev_template.shape[:2]
    dev_center_y = dev_y + dev_h / 2
    _log(f"Đã tìm thấy thiết bị '{device_choice}' tại Y={dev_center_y:.1f}. Đang quét nút RDP...")

    res_rdp = cv2.matchTemplate(scene, rdp_template, cv2.TM_CCOEFF_NORMED)
    threshold = 0.65
    locs_rdp = np.where(res_rdp >= threshold)

    # De-duplicate các điểm gần nhau
    rdp_pts: list[tuple[tuple, tuple]] = []
    for pt in zip(*locs_rdp[::-1]):
        if not any(
            abs(pt[1] - ex[0][1]) < 10 and abs(pt[0] - ex[0][0]) < 10
            for ex in rdp_pts
        ):
            rdp_pts.append((pt, rdp_template.shape[:2]))

    # Tìm nút RDP có Y gần nhất với dòng thiết bị (trong phạm vi ±45px)
    best_rdp = None
    min_dist_y = float("inf")
    for pt, shape in rdp_pts:
        rdp_h, rdp_w = shape
        rdp_center_y = pt[1] + rdp_h / 2
        dist_y = abs(rdp_center_y - dev_center_y)
        if dist_y < 45 and dist_y < min_dist_y:
            min_dist_y = dist_y
            best_rdp = (pt, shape)

    del dev_template, rdp_template, res_dev, res_rdp
    gc.collect()

    if not best_rdp:
        _log("Không tìm thấy nút RDP cùng dòng với thiết bị đã chọn.")
        return None

    pt, shape = best_rdp
    rdp_h, rdp_w = shape
    click_x = int(pt[0] + rdp_w / 2)
    click_y = int(pt[1] + rdp_h / 2)
    _log(f"Xác định nút RDP tại ({click_x}, {click_y}) — cách dòng thiết bị {min_dist_y:.1f}px.")
    return click_x, click_y
