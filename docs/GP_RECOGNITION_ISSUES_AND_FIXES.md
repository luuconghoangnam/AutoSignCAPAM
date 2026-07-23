# 🛠️ Phân Tích Vấn Đề Nhập Liệu GlobalProtect & Phương Án Khắc Phục

Tài liệu này ghi nhận chi tiết **các nguyên nhân gây lỗi click lệch, nhập quá nhanh/mất chữ trên GlobalProtect** và **hướng dẫn cách sửa mã nguồn** để triển khai trên môi trường Windows.

---

## 🔍 1. Phân Tích Nguyên Nhân Kỹ Thuật (Root Causes)

### ❌ Vấn Đề 1: Click Nhập Lệch Vị Trí / Sai Ô Input
- **Hiện trạng trong Code**: Trong [vision/field_detector.py](file:///home/gone/NewVolume_200G/repos/ToolsSignCAPAM/vision/field_detector.py), nhận diện ô input của GlobalProtect hiện dùng thuật toán **Canny Edge Detection** (`cv2.Canny`) và **Pixel Fallback** thuần túy:
  ```python
  edged = cv2.Canny(blurred, 50, 150)
  contours, _ = cv2.findContours(...)
  ```
- **Nguyên nhân**:
  1. **Không có ảnh Template tham chiếu cố định**: Tool chỉ dò "các khung hình chữ nhật có tỷ lệ chiều rộng/chiều cao tương đối", chứ không hề có ảnh mẫu chuẩn của ô nhập liệu GlobalProtect.
  2. Khi giao diện Windows (Win 10 / Win 11) hoặc theme GlobalProtect thay đổi, các đường viền mờ (Flat UI) hoặc các khung chữ nhật khác trên giao diện GP dễ bị OpenCV quét nhầm làm ô input -> Dẫn đến click lệch vị trí.

---

### ❌ Vấn Đề 2: Nhập Quá Nhanh / Windows Không Kịp Nhận / Dán Thiếu Ký Tự
- **Hiện trạng trong Code**:
  1. Trong [config.py](file:///home/gone/NewVolume_200G/repos/ToolsSignCAPAM/config.py#L48-L68) (`write_text_safely`), khoảng thời gian chờ (delay) khi sao chép và dán bằng Clipboard (`Ctrl+V`) quá ngắn:
     ```python
     pyperclip.copy(text)
     time.sleep(0.05)  # 50ms -> Quá nhanh!
     pyautogui.hotkey("ctrl", "v")
     time.sleep(0.05)  # 50ms -> Quá nhanh!
     ```
  2. Trong [core/gp_handler.py](file:///home/gone/NewVolume_200G/repos/ToolsSignCAPAM/core/gp_handler.py#L348-L366) (`enter_credentials`), khoảng nghỉ giữa việc Click ô Username -> Xóa chữ cũ -> Dán chữ mới -> Click ô Password diễn ra dồn dập.
- **Nguyên nhân**: Khi CPU bận hoặc Windows đang xử lý sự kiện focus cửa sổ, khoảng delay `50ms` (`0.05s`) làm lệnh `Ctrl+V` phát ra trước khi dữ liệu clipboard kịp ghi nhận, hoặc chưa đủ thời gian để bộ gõ/Windows nhận diện event Paste -> Dẫn đến ô input bị bỏ trống hoặc dán thiếu ký tự.

---

## 💡 2. Đề Xuất Phương Án Khắc Phục (Proposed Solutions)

### 🛠️ Giải Pháp 1: Tăng Delay & Thêm Khoảng Nghỉ Nhập Liệu (Tối Ưu Ngay)

Cần nâng thời gian chờ trong `config.py` và `gp_handler.py` lên khoảng **`150ms - 200ms`** để Windows nhận diện sự kiện phím mượt mà hơn.

#### A. Sửa `config.py` (`write_text_safely`):
```python
def write_text_safely(text: str, target_active=None) -> bool:
    if not text:
        return True
    import pyperclip
    import pyautogui
    import time

    old_clipboard = ""
    try:
        old_clipboard = pyperclip.paste()
    except Exception:
        pass

    try:
        pyperclip.copy(text)
        time.sleep(0.15)  # Tăng từ 0.05s lên 0.15s để Clipboard kịp ghi nhận
        if target_active and not target_active():
            return False
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.15)  # Tăng từ 0.05s lên 0.15s để Windows xử lý Paste
    except Exception:
        if target_active and not target_active():
            return False
        pyautogui.write(text, interval=0.05) # Tăng interval gõ phím fallback
    finally:
        try:
            pyperclip.copy(old_clipboard if old_clipboard else "")
        except Exception:
            pass
    return True
```

#### B. Sửa `core/gp_handler.py` (`enter_credentials`):
Thêm `time.sleep(0.15)` - `time.sleep(0.2)` sau mỗi thao tác Click, Ctrl+A, Backspace để ứng dụng GP có đủ thời gian phản hồi:
```python
# Ví dụ khi điền ô Username:
pyautogui.moveTo(click_x0, click_y0, duration=0.25)
pyautogui.click()
time.sleep(0.2) # Chờ focus ô Username

pyautogui.hotkey("ctrl", "a")
time.sleep(0.1)
pyautogui.press("backspace")
time.sleep(0.1)

if not write_text_safely(username, lambda: self.adapter.is_foreground(rect)):
    return False

time.sleep(0.2) # Khoảng nghỉ trước khi chuyển sang ô Password

# Ví dụ khi điền ô Password:
pyautogui.moveTo(click_x1, click_y1, duration=0.25)
pyautogui.click()
time.sleep(0.2) # Chờ focus ô Password

pyautogui.hotkey("ctrl", "a")
time.sleep(0.1)
pyautogui.press("backspace")
time.sleep(0.1)

if not write_text_safely(password, lambda: self.adapter.is_foreground(rect)):
    return False
```

---

### 🛠️ Giải Pháp 2: Bổ Sung Ảnh Template Tham Chiếu Cho GlobalProtect

Tương tự như cách dự án đang dùng `template_200.png` và `template_rdp.png` cho CAPAM RDP, chúng ta sẽ thêm phương pháp **Template Matching** cho GlobalProtect để chuẩn xác 100%.

#### Các bước thực hiện:
1. **Chụp ảnh mẫu (Screenshots)**:
   - Chụp ảnh mẫu nhãn/ô input Username/Password thực tế của GlobalProtect trên Windows.
   - Lưu vào thư mục gốc dự án: `template_gp_user.png`, `template_gp_pass.png` (hoặc `template_gp_portal.png`).
2. **Cập nhật `core/gp_handler.py`**:
   - Trước khi dùng OpenCV Canny Edge, cho tool dùng `vision/template_matcher.py` tìm vị trí ô input theo ảnh mẫu `template_gp_user.png` / `template_gp_pass.png`.
   - Nếu tìm thấy vị trí khớp với độ tin cậy `confidence >= 0.8` -> Lấy trực tiếp tọa độ đó để Click.
   - Nếu không thấy -> Fallback sang dùng `detect_input_fields()` (Canny edge contour).

---

## 📋 3. Check-list Các Việc Cần Làm Khi Chuyển Sang Máy Windows

- [x] **Bước 1**: Mở `config.py` và sửa delay của `write_text_safely` từ `0.05` -> `0.15`.
- [x] **Bước 2**: Mở `core/gp_handler.py` và bổ sung thêm các dòng `time.sleep(0.15)` - `time.sleep(0.2)` giữa các bước Click & gõ phím.
- [x] **Bước 3**: Chụp ảnh màn hình cửa sổ GlobalProtect thực tế trên máy Windows, cắt riêng ô nhập liệu và lưu thành `template_gp_user.png` / `template_gp_pass.png`.
- [x] **Bước 4**: Thêm bước Template Matching vào `GPHandler.enter_credentials()` trước khi fallback sang OpenCV Contour.
- [x] **Bước 5**: Chạy thử `python main.py` kiểm tra độ mượt và chính xác khi đăng nhập GP.

---
> 📌 *Tài liệu được khởi tạo tự động để hỗ trợ chuyển giao mã nguồn sang môi trường máy làm việc Windows.*
