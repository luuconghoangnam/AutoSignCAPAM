# Hướng dẫn Calibrate & Cấu hình Nhận diện (Train Template) cho Windows/Môi trường mới

Tài liệu này hướng dẫn chi tiết cách tự chụp ảnh mẫu (template), hiệu chỉnh thông số và tối ưu hóa hệ thống nhận diện của phần mềm khi chuyển sang chạy trên **Windows** hoặc các máy có **độ phân giải màn hình (Resolution)** và **tỉ lệ thu phóng (DPI Scaling)** khác nhau.

---

## 🗺️ Cơ chế hoạt động của Bộ nhận diện

Phần mềm sử dụng 2 cơ chế chính để điều khiển tự động:
1. **Template Matching (Khớp ảnh mẫu):** Tìm dòng thiết bị (`10.64.211.200` hoặc `10.64.211.12`) và tìm nút bấm **[RDP]** tương ứng bên cạnh để click.
2. **Contour Detection (Phát hiện đường biên):** Quét động các ô nhập mật khẩu/tài khoản trên giao diện CAPAM Login và bảng Windows Security dựa trên hình khối hộp (không dùng ảnh mẫu tĩnh).

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

## 2. Hiệu chỉnh thông số Contour (Nhận diện ô Input)

Nếu phần mềm tìm thấy cửa sổ CAPAM/Windows Security nhưng **không tự điền được Username/Password**, nguyên nhân là do kích thước pixel của các ô nhập liệu trên Windows khác với Linux.

### Đoạn code cấu hình trong `main_automation.py` (Hàm `detect_capam_fields`):

```python
# Dòng ~409 trong main_automation.py
for c in contours:
    x, y, w, h = cv2.boundingRect(c)
    # Kích thước ô nhập liệu cần nhận dạng (Width từ 80-280px, Height từ 12-40px)
    if 80 <= w <= 280 and 12 <= h <= 40:
        fields.append((x, y, w, h))
```

### Cách Calibrate:
- **Nếu ô nhập liệu của Windows Security quá ngắn hoặc quá dài:** Đo kích thước thực tế của ô nhập liệu (bằng cách chụp ảnh màn hình và xem kích thước pixel trong Paint).
- **Điều chỉnh điều kiện lọc:** 
  - Nếu ô nhập liệu rộng 350px → Tăng giới hạn `w <= 280` lên `w <= 380`.
  - Nếu chiều cao ô nhập liệu nhỏ hơn 12px → Giảm giới hạn `12 <= h` xuống `8 <= h`.

---

## 3. Tinh chỉnh độ nhạy Nhận diện (Threshold)

Độ nhạy khớp ảnh được cấu hình bằng biến `threshold` (từ `0.0` đến `1.0`).
*   `1.0`: Khớp tuyệt đối 100% (rất khó đạt được nếu có lệch DPI/font rendering).
*   `0.6 - 0.7`: Khớp tương đối (khuyến nghị).
*   `< 0.5`: Dễ nhận diện nhầm các chi tiết khác trên màn hình.

### Các vị trí cần điều chỉnh trong `main_automation.py`:

1. **Độ khớp IP Thiết bị (Dòng ~303):**
   ```python
   if max_val_dev < 0.65: # Tăng lên 0.75 nếu bị nhận diện sai thiết bị, giảm xuống 0.55 nếu không tìm thấy
   ```
2. **Độ khớp Nút RDP (Dòng ~314):**
   ```python
   threshold = 0.65 # Có thể hạ xuống 0.60 nếu nút RDP trên Windows có màu hơi khác
   ```

---

## 4. Xử lý lệch tọa độ Click (DPI Scaling Windows)

Trên Windows, khi bật tính năng phóng to màn hình (DPI Scaling 125%, 150%), tọa độ click của PyAutoGUI có thể bị lệch so với tọa độ OpenCV tìm được.

### Cách khắc phục:
Thêm đoạn code sau vào ngay dưới phần import trong `main_automation.py` để ép Windows chạy ở chế độ tọa độ chuẩn (DPI Aware):

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
