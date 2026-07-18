# Hướng dẫn Calibrate & Cấu hình Nhận diện (Train Template) cho Windows/Môi trường mới

Tài liệu này hướng dẫn chi tiết cách tự chụp ảnh mẫu (template), hiệu chỉnh thông số và tối ưu hóa hệ thống nhận diện của phần mềm khi chuyển sang chạy trên **Windows** hoặc các máy có **độ phân giải màn hình (Resolution)** và **tỉ lệ thu phóng (DPI Scaling)** khác nhau.

---

## 🗺️ Cơ chế hoạt động của Bộ nhận diện

Runtime hiện tại dùng ba cơ chế:
1. **Template Matching:** Tìm dòng thiết bị và nút RDP cùng hàng, có quét nhiều scale.
2. **Contour Detection:** Nhận diện field GlobalProtect/CAPAM khi semantic backend không đủ dữ liệu.
3. **Guarded Keyboard:** Điền Windows Security theo focus mặc định, kiểm tra exact HWND và postcondition.

---

## 1. Hướng dẫn chụp và thay thế Template PNG (Train ảnh mẫu)

Khi chạy trên máy tính mới (đặc biệt là Windows), font chữ render và kích thước giao diện CAPAM có thể thay đổi khiến thuật toán không khớp được ảnh cũ (lỗi: *Không tìm thấy nhãn thiết bị* hoặc *độ khớp thấp*).

### Các ảnh mẫu cần chụp lại:
1. **`template_200.png`**: Ảnh cắt nhãn IP của thiết bị 200 (Thường là đoạn text `10.64.211.200` trong danh sách).
2. **`template_12.png`**: Ảnh cắt nhãn IP của thiết bị 12 (Thường là đoạn text `10.64.211.12` trong danh sách).
3. **`template_rdp.png`**: Ảnh cắt nút bấm kết nối **[RDP]** (nút nhỏ màu xanh/xám có biểu tượng màn hình hoặc chữ RDP bên phải).

### 🛠️ Quy trình chụp chuẩn trên Windows:

1. **Thiết lập DPI & Độ phân giải:**
   - Đảm bảo màn hình Windows đang để độ phân giải chuẩn của người dùng (ví dụ: `1920x1080`).
   - Kiểm tra DPI Scaling trong **Display settings** (thường là `100%` hoặc `125%`). Khi đã chụp template ở mức scale nào thì phần mềm sẽ hoạt động chuẩn nhất ở mức scale đó.
2. **Mở CAPAM Client:**
   - Đăng nhập thủ công CAPAM đến bước danh sách thiết bị. 
   - Đảm bảo danh sách hiển thị rõ ràng, không bị che khuất bởi cửa sổ khác.
3. **Cắt ảnh bằng Snipping Tool:**
   - Nhấn tổ hợp phím `Windows + Shift + S`.
   - Chọn chế độ cắt hình chữ nhật.
   - **Cách cắt IP:** Cắt sát biên chữ số, không lấy khoảng trắng dư thừa ở trên/dưới.
     *(Ví dụ: chỉ khoanh vùng chứa đúng chữ `10.64.211.200`)*
   - **Cách cắt nút RDP:** Cắt trọn vẹn icon nút RDP. Chỉ cắt **1 nút duy nhất**.
4. **Lưu và Thay thế:**
   - Lưu các file với đúng tên định dạng: `template_200.png`, `template_12.png`, `template_rdp.png`.
   - Copy đè các file này vào thư mục gốc của dự án `ToolsSignCAPAM/`.

---

## 2. Hiệu chỉnh Contour fallback

Nếu phần mềm tìm thấy GlobalProtect/CAPAM nhưng không resolve được field, kiểm tra detector fallback. Windows Security không dùng detector này.

### Đoạn code cấu hình hiện tại trong `vision/field_detector.py`:

Detector dùng tỉ lệ width/height theo kích thước ảnh cửa sổ và ngưỡng sáng theo profile. Không chỉnh bằng pixel tuyệt đối nếu chưa có regression images ở DPI 100%, 125% và 150%.

### Cách Calibrate legacy:

Field detector hiện tại vẫn giữ làm fallback. Hybrid detector trong `hybrid_windows_automation_architecture_plan.md` sẽ thay dần việc chỉnh ngưỡng pixel thủ công.
- Lưu screenshot cửa sổ đích trước khi nhập credential.
- Ghi Windows build, DPI, font scale và kích thước HWND.
- Điều chỉnh `ratio_limits`/`_MIN_MEAN` trong `vision/field_detector.py`.
- Chạy lại toàn bộ ảnh calibration, không chỉ ảnh đang fail.

---

## 3. Tinh chỉnh độ nhạy Nhận diện (Threshold)

Độ nhạy khớp ảnh được cấu hình bằng biến `threshold` (từ `0.0` đến `1.0`).
*   `1.0`: Khớp tuyệt đối 100% (rất khó đạt được nếu có lệch DPI/font rendering).
*   `0.6 - 0.7`: Khớp tương đối (khuyến nghị).
*   `< 0.5`: Dễ nhận diện nhầm các chi tiết khác trên màn hình.

`vision/template_matcher.py` nhận candidate từ `0.65`; `core/rdp_handler.py` chỉ cho action khi device và RDP cùng đạt `0.70`, target ổn định hai frame. Không hạ action threshold nếu chưa kiểm tra false-positive cùng hàng.

---

## 4. Xử lý lệch tọa độ Click (DPI Scaling Windows)

Trên Windows, khi bật tính năng phóng to màn hình (DPI Scaling 125%, 150%), tọa độ click của PyAutoGUI có thể bị lệch so với tọa độ OpenCV tìm được.

### Cách khắc phục:
DPI awareness đã được cấu hình trong `config.py`, import trước khi tạo QApplication. Không thêm lần nữa ở module khác:

```python
import platform
if platform.system() == "Windows":
    import ctypes
    try:
        # Thiết lập chế độ Per-Monitor DPI Aware
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            # Fallback cho phiên bản Windows cũ hơn
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
```

---

## 5. Kịch bản Test nhanh trên Windows (Không cần chạy cả luồng)

Tạo một file test nhanh tên là `test_match.py` trong thư mục dự án trên Windows để kiểm tra xem ảnh mẫu đã khớp chưa trước khi chạy app chính:

```python
import cv2
import numpy as np
import pyautogui

# 1. Chụp màn hình hiện tại
screenshot = pyautogui.screenshot()
scene = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

# 2. Đọc ảnh mẫu
template = cv2.imread("template_200.png")

if template is None:
    print("Lỗi: Không tìm thấy file template_200.png!")
    exit()

# 3. Chạy Match
res = cv2.matchTemplate(scene, template, cv2.TM_CCOEFF_NORMED)
min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

print(f"Độ khớp lớn nhất tìm được: {max_val:.4f}")
if max_val >= 0.65:
    print(f"Khớp THÀNH CÔNG tại tọa độ: {max_loc}")
else:
    print("Khớp THẤT BẠI. Hãy chụp lại ảnh mẫu!")
```
