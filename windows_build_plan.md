# Kế hoạch Build Bản Windows - CAPAM Auto-Sign Tool

## 1. Đánh giá Hiện trạng

### ✅ Đã có sẵn (hoạt động tốt)
| Thành phần | Trạng thái |
|---|---|
| `WindowsAdapter` class | ✅ Đã implement đầy đủ (`focus_window`, `get_window_rect`, `take_screenshot`, `launch_capam`, `launch_gp_ui`) |
| Platform detection | ✅ `get_os_adapter()` tự động dùng `WindowsAdapter` khi chạy trên Windows |
| `build_windows.bat` | ✅ Đã có script build PyInstaller với `--add-data` dùng dấu `;` đúng chuẩn Windows |
| `requirements.txt` | ✅ `pygetwindow` và `pillow` chỉ install trên Windows (`sys_platform == 'win32'`) |
| Template matching logic | ✅ Dùng OpenCV, không phụ thuộc OS |
| GUI (PyQt5) | ✅ Cross-platform, chạy nguyên trên Windows |

### ⚠️ Cần kiểm tra / Tiềm ẩn rủi ro

| Vấn đề | Chi tiết | Mức độ |
|---|---|---|
| **Template ảnh** | Các file `template_200.png`, `template_12.png`, `template_rdp.png` được chụp trên **màn hình Linux** (DPI, font rendering khác) → Có thể không khớp trên Windows | 🔴 Cao |
| **Tên cửa sổ CAPAM** | `WindowsAdapter.get_window_rect("Symantec Privileged Access Manager")` — cần xác nhận title bar trên Windows có khớp không | 🟡 Trung bình |
| **Đường dẫn CAPAM Client** | Hardcode `C:\Program Files\Broadcom\CAPAM Client\CAPAMClient.exe` — cần kiểm tra tên thư mục cài đặt thực tế trên máy Windows | 🟡 Trung bình |
| **`pygetwindow` quirks** | Trên Windows, `gw.getWindowsWithTitle()` match substring, đôi khi trả về nhiều cửa sổ không đúng | 🟡 Trung bình |
| **Windows Security dialog** | Dialog `"Windows Security"` — cần test `get_window_rect` có tìm được không | 🟡 Trung bình |
| **`ImageGrab` trên multi-monitor** | `PIL.ImageGrab.grab()` mặc định chỉ chụp màn hình primary — nếu CAPAM trên màn hình phụ thì sai | 🟠 Thấp-Trung |
| **Anti-virus / UAC** | Một số AV chặn PyInstaller EXE không có chữ ký số | 🟠 Thấp |

### ❌ Không tương thích (cần bỏ qua trên Windows)
| Thành phần Linux | Thay thế trên Windows |
|---|---|
| `maim` (chụp màn hình) | `PIL.ImageGrab.grab()` — đã implement trong `WindowsAdapter` |
| `wmctrl` (quản lý cửa sổ) | `pygetwindow` — đã implement |
| `dbus-python` (GP tray) | `subprocess.Popen(["PanGPA.exe"])` — đã implement |

---

## 2. Các bước thực hiện

### Bước 1 — Chuẩn bị môi trường Windows

```batch
:: Yêu cầu: Python 3.10+ đã cài sẵn
:: Kiểm tra version
python --version

:: Clone repo
git clone https://github.com/luuconghoangnam/ToolsSignCAPAM.git
cd ToolsSignCAPAM

:: Cài dependencies
pip install -r requirements.txt
```

> **Lưu ý:** Cần cài `Visual C++ Redistributable` nếu chưa có (PyInstaller yêu cầu).

---

### Bước 2 — Chụp lại Template từ CAPAM Client trên Windows

Đây là bước **quan trọng nhất**. Template chụp trên Linux sẽ không khớp trên Windows vì:
- Font rendering khác nhau (ClearType vs FreeType)
- DPI Windows thường là 96-125 DPI vs 96 DPI Linux
- Giao diện CAPAM Client có thể khác version

**Cách chụp template mới trên Windows:**

1. Mở CAPAM Client lên màn hình Danh sách thiết bị
2. Dùng **Snipping Tool** (Win+Shift+S) cắt chính xác:
   - `template_200.png`: Phần chữ `10.64.211.200` trong cột Address
   - `template_12.png`: Phần chữ `10.64.211.12` trong cột Address  
   - `template_rdp.png`: Icon nút RDP (cột RDP Applications) — chỉ cắt 1 nút
3. Thay thế 3 file template trong thư mục repo

**Tiêu chí ảnh chuẩn:**
- Không có viền trắng thừa
- Kích thước tối thiểu 20×10px
- Nền không bị blur

---

### Bước 3 — Xác nhận đường dẫn và title cửa sổ

Mở PowerShell, chạy để lấy title cửa sổ CAPAM đang mở:

```powershell
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.Screen]::AllScreens
# Và:
Get-Process | Where-Object {$_.MainWindowTitle -like "*CAPAM*" -or $_.MainWindowTitle -like "*Symantec*"} | Select-Object Name, MainWindowTitle
```

Nếu title khác với `"Symantec Privileged Access Manager"`, cần cập nhật trong code:

```python
# main_automation.py - tìm dòng này và sửa title
rect_capam = self.os_tool.get_window_rect("Symantec Privileged Access Manager")
```

---

### Bước 4 — Test chạy trực tiếp từ Python

Trước khi build EXE, test chạy từ source:

```batch
python main_automation.py
```

Kiểm tra checklist:
- [ ] Giao diện hiện lên đúng, không bị vỡ
- [ ] Nhập Username/Password/IP/OTP được
- [ ] Click "Tiến hành đăng nhập" không crash
- [ ] Logs hiển thị đúng quá trình
- [ ] Template matching tìm được máy đích
- [ ] Click nút RDP thành công
- [ ] Bảng Windows Security tự điền được

---

### Bước 5 — Build EXE

```batch
build_windows.bat
```

Output: `dist\CAPAM_AutoSign_Windows.exe`

**Nếu bị lỗi build**, thử thêm flag:
```batch
pyinstaller --noconsole --onefile ^
    --add-data "template_rdp.png;." ^
    --add-data "template_200.png;." ^
    --add-data "template_12.png;." ^
    --hidden-import=PIL._tkinter_finder ^
    --hidden-import=pygetwindow ^
    --name "CAPAM_AutoSign_Windows" ^
    main_automation.py
```

---

### Bước 6 — Test EXE

Chạy `dist\CAPAM_AutoSign_Windows.exe` và kiểm tra lại toàn bộ checklist ở Bước 4.

Nếu EXE bị AV chặn:
1. Thêm exception trong Windows Defender
2. Hoặc ký số EXE bằng self-signed certificate (nâng cao)

---

## 3. Điểm khác biệt có thể cần sửa code

### 3.1. Multi-monitor support (nếu cần)

```python
# Hiện tại (WindowsAdapter.take_full_screenshot):
from PIL import ImageGrab
ImageGrab.grab().save(path)

# Sửa để hỗ trợ tất cả màn hình:
ImageGrab.grab(all_screens=True).save(path)
```

### 3.2. Xử lý DPI scaling trên Windows

Nếu máy dùng DPI > 100%, tọa độ click bị lệch. Thêm vào đầu `main_automation.py`:

```python
if platform.system() == "Windows":
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor DPI aware
```

### 3.3. Đường dẫn CAPAM nếu cài ở vị trí khác

```python
# WindowsAdapter.launch_capam() - cần xác nhận đường dẫn thực tế
capam_path = r"C:\Program Files\Broadcom\CAPAM Client\CAPAMClient.exe"
# Có thể là:
# r"C:\Program Files (x86)\Broadcom\CAPAM Client\CAPAMClient.exe"
```

---

## 4. Checklist Tổng hợp trước khi phát hành

| # | Hạng mục | Trạng thái |
|---|---|---|
| 1 | Chụp lại 3 template từ CAPAM Client trên Windows | ⬜ |
| 2 | Test `python main_automation.py` chạy thành công | ⬜ |
| 3 | Xác nhận title cửa sổ CAPAM đúng | ⬜ |
| 4 | Template matching tìm được máy 200 và 12 | ⬜ |
| 5 | Click RDP → Windows Security dialog xuất hiện | ⬜ |
| 6 | Tự điền User/Pass vào Windows Security | ⬜ |
| 7 | Build `build_windows.bat` thành công | ⬜ |
| 8 | Test EXE không bị AV chặn | ⬜ |
| 9 | Test trên máy sạch (chưa cài Python) | ⬜ |
| 10 | Commit template Windows lên repo (nhánh `windows` riêng) | ⬜ |

---

## 5. Khuyến nghị

> **Nên dùng nhánh `windows` riêng trên GitHub** để lưu template Windows, tránh xung đột với template Linux trên `main`. Người dùng tải đúng bản phù hợp hệ điều hành.

```bash
git checkout -b windows
# Thay 3 file template Windows vào
git add template_*.png
git commit -m "feat(windows): cập nhật template từ CAPAM Client trên Windows"
git push origin windows
```
