# Báo cáo Bảo mật — CAPAM Auto-Sign Tool

> **Phạm vi:** Phân tích bảo mật mã nguồn hiện tại trong `main.py`, `core/`, `adapters/`, `vision/` và `ui/`.
> **Mức độ rủi ro:** Dùng thang 🔴 Cao / 🟠 Trung bình / 🟡 Thấp / 🟢 Chấp nhận được

---

## Tóm tắt điều hành

| Mức độ | Số lượng phát hiện |
|---|---|
| 🔴 Cao | 2 |
| 🟠 Trung bình | 4 |
| 🟡 Thấp | 3 |
| 🟢 Thông tin | 2 |

Công cụ này được thiết kế để **tự động hóa quy trình đăng nhập nội bộ**, xử lý thông tin xác thực nhạy cảm (username, password, OTP). Toàn bộ hoạt động diễn ra **cục bộ trên máy người dùng**, không có server backend hay API bên ngoài — đây là điểm mạnh về bảo mật. Tuy nhiên, một số rủi ro cần được xử lý trước khi triển khai rộng.

---

## 1. 🟢 Mật khẩu không còn được lưu tự động

**File liên quan:** `ui/main_window.py` → `_save_settings()`, `~/.capam_autosign_settings.json`

**Trạng thái:** Đã xử lý trong `ui/main_window.py`. `_save_settings()` chỉ lưu username, CAPAM IP và tùy chọn UI; password không còn được ghi vào JSON. File cũ trên máy người dùng vẫn có thể chứa password và cần được xóa thủ công hoặc migrate.

**Việc còn lại:**

- Nếu cần ghi nhớ password, dùng `keyring` (Windows Credential Manager/KWallet), không dùng JSON:
  ```python
  import keyring
  keyring.set_password("capam_autosign", username, password)
  password = keyring.get_password("capam_autosign", username)
  ```
`keyring` tự động dùng KWallet (Linux), Credential Manager (Windows).

---

## 2. 🔴 OTP truyền qua tham số hàm (lưu trong memory)

**File liên quan:** `core/state_machine.py`, `ui/main_window.py`

**Mô tả:**  
OTP 6 số được lưu như thuộc tính `self.otp` của thread worker trong suốt quá trình automation, không được xóa sau khi sử dụng xong:

```python
self.worker = AutomationWorker(username, password_prefix, otp, choice, capam_ip)
# self.otp tồn tại trong memory cho đến khi GC thu hồi
```

**Rủi ro:**  
Tuy OTP có thời hạn ngắn (30–60 giây), nhưng trên lý thuyết có thể bị đọc từ memory dump nếu máy bị tấn công trong thời điểm đó.

**Đề xuất khắc phục:**

```python
# Xóa OTP khỏi thuộc tính ngay sau khi đã sử dụng lần đầu
pyautogui.write(self.otp, interval=0.03)
self.otp = ""  # Xóa ngay
```

---

## 3. 🟠 Chụp màn hình toàn bộ tại thời điểm automation

**File liên quan:** `vision/field_detector.py`, `adapters/windows.py`, `adapters/linux.py`

**Mô tả:**  
Trong quá trình tự động hóa, công cụ chụp ảnh màn hình đầy đủ (`maim` trên Linux, `PIL.ImageGrab` trên Windows) để phát hiện cửa sổ và ô nhập liệu.

**Rủi ro:**  
Nếu người dùng đang mở các màn hình chứa thông tin nhạy cảm (email, tài liệu mật, chat nội bộ) thì các ảnh chụp này có thể vô tình ghi lại nội dung đó — dù chỉ lưu tạm thời trong RAM (không ghi ra đĩa trong flow hiện tại).

**Đề xuất khắc phục:**

- Chỉ chụp vùng cửa sổ CAPAM cụ thể (không chụp toàn màn hình) bằng cách sử dụng tọa độ `rect` đã biết:
  ```python
  # Thay take_full_screenshot → take_screenshot(rect) khi đã có rect
  self.os_tool.take_screenshot(rect_capam, path)
  ```
- Đảm bảo không ghi ảnh ra đĩa trong môi trường production (hiện tại đã không ghi, chỉ dùng temp file trong memory).

---

## 4. 🟠 Không xác thực server CAPAM (Man-in-the-Middle)

**File liên quan:** `core/gp_handler.py`, flow kiểm tra kết nối CAPAM

**Mô tả:**  
Công cụ kiểm tra kết nối mạng đến server CAPAM bằng TCP socket thuần:

```python
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((host, port))
```

Không có xác thực TLS certificate hay fingerprint của server CAPAM.

**Rủi ro:**  
Trong môi trường mạng nội bộ bị xâm phạm, có thể bị chuyển hướng đến server giả mạo (giả IP 10.64.213.188), thu thập thông tin đăng nhập.

**Đề xuất khắc phục:**

- Thêm kiểm tra TLS khi kết nối:
  ```python
  import ssl
  ctx = ssl.create_default_context()
  with ctx.wrap_socket(socket.socket(), server_hostname=host) as s:
      s.connect((host, 443))
  ```
- Hoặc chấp nhận rủi ro này nếu môi trường mạng nội bộ đã được kiểm soát chặt (VLAN, firewall nội bộ).

---

## 5. 🟠 Quyền kiểm soát chuột/bàn phím toàn hệ thống

**File liên quan:** `pyautogui.write()`, `pyautogui.click()`, `pyautogui.hotkey()`

**Mô tả:**  
`pyautogui` hoạt động ở mức OS, kiểm soát toàn bộ chuột và bàn phím không phụ thuộc vào cửa sổ nào đang active.

**Rủi ro:**  
Nếu người dùng vô tình click vào cửa sổ khác trong khi automation đang chạy, các phím/click có thể tác động vào ứng dụng sai (gửi mật khẩu vào cửa sổ không mong muốn, xóa dữ liệu đang soạn thảo...).

**Đề xuất khắc phục (đã có một phần):**

- Hiện tại đã `showMinimized()` cửa sổ tool trước khi automation — tốt.
- Nên thêm `pyautogui.FAILSAFE = True` (mặc định đã bật): di chuột lên góc trên-trái màn hình sẽ dừng ngay lập tức.
- Thêm delay giữa các thao tác và kiểm tra focus trước khi gõ phím:
  ```python
  # Đảm bảo focus đúng cửa sổ trước khi gõ
  self.os_tool.focus_window("Symantec Privileged Access Manager")
  time.sleep(0.3)
  pyautogui.write(self.password_prefix, interval=0.04)
  ```

---

## 6. 🟠 Không giới hạn số lần thử đăng nhập

**File liên quan:** `core/state_machine.py`, `core/gp_handler.py`

**Mô tả:**  
Nếu OTP sai, mật khẩu sai hoặc kết nối thất bại, công cụ báo lỗi và dừng — không retry tự động sai OTP. Tuy nhiên, **không có cơ chế giới hạn** nếu người dùng chạy lại nhiều lần liên tiếp với OTP sai.

**Rủi ro:**  
Server CAPAM có thể khóa tài khoản sau nhiều lần đăng nhập thất bại (account lockout policy). Người dùng vô tình có thể tự khóa tài khoản của mình.

**Đề xuất khắc phục:**

- Thêm cảnh báo trong log khi phát hiện đăng nhập thất bại lặp lại:
  ```python
  self.log("⚠️ Cảnh báo: Nhập sai OTP hoặc mật khẩu nhiều lần có thể khóa tài khoản!")
  ```
- Không tự retry khi OTP/password sai (đã đúng — chỉ retry khi timeout kỹ thuật).

---

## 7. 🟡 File settings không mã hóa metadata

**File liên quan:** `~/.capam_autosign_settings.json`

**Mô tả:**  
File JSON lưu username (dạng plaintext) và IP server. Dù ít nguy hiểm hơn mật khẩu, nhưng username và IP nội bộ là thông tin trinh sát (reconnaissance) có giá trị.

**Đề xuất khắc phục:**

```python
# Tối thiểu: set permission 600 khi tạo file
os.chmod(self.settings_file, 0o600)
```

---

## 8. 🟡 Template PNG có thể bị giả mạo

**File liên quan:** `template_200.png`, `template_12.png`, `template_rdp.png`

**Mô tả:**  
Các file template PNG được dùng để phát hiện UI elements qua OpenCV. Nếu kẻ tấn công thay thế các file này bằng template giả, công cụ có thể click vào vùng sai trên màn hình.

**Rủi ro:** Thấp trong môi trường nội bộ, nhưng cần lưu ý khi chia sẻ binary.

**Đề xuất khắc phục:**

- Nhúng template vào binary (đã là default trong PyInstaller `--add-data`).
- Trong bản Native Go: dùng `//go:embed` để template không thể bị thay thế từ bên ngoài.

---

## 9. 🟡 Log in-app có thể chứa thông tin nhạy cảm

**File liên quan:** `txt_logs` QTextEdit, hàm `log()`

**Mô tả:**  
Nếu log vô tình ghi thông tin như tên máy, IP, hoặc trạng thái đăng nhập, người ngồi cạnh có thể đọc.

**Đề xuất khắc phục:**

- Đã ẩn password trong log (không ghi password ra log) — tốt.
- Không log OTP — cần kiểm tra lại để đảm bảo không log `self.otp` trong bất kỳ log statement nào.

---

## 10. 🟢 Điểm tốt đã có sẵn

| Điểm tốt | Chi tiết |
|---|---|
| Không có server backend | Toàn bộ xử lý cục bộ, không gửi thông tin ra ngoài |
| Password không log | Không ghi mật khẩu vào log area |
| OTP không lưu vào settings | OTP chỉ tồn tại trong bộ nhớ trong 1 phiên |
| `pyautogui.FAILSAFE` | Di chuột góc trên-trái = dừng ngay (mặc định bật) |
| Minimize khi automation | Giảm nguy cơ tác động ngoài ý muốn |
| Open source | Người dùng có thể audit code |

---

## 11. Đề xuất Ưu tiên

| # | Hành động | Độ ưu tiên | Độ phức tạp |
|---|---|---|---|
| 1 | Dùng `keyring` thay plaintext password | 🔴 Cao | Thấp (2 dòng code) |
| 2 | `chmod 600` file settings ngay khi tạo | 🔴 Cao | Rất thấp (1 dòng) |
| 3 | Xóa `self.otp = ""` sau khi dùng | 🟠 Trung bình | Rất thấp |
| 4 | Chỉ chụp vùng cửa sổ CAPAM, không chụp toàn màn hình | 🟠 Trung bình | Thấp |
| 5 | Thêm cảnh báo lockout trong log | 🟠 Trung bình | Rất thấp |
| 6 | Kiểm tra focus trước khi gõ phím | 🟠 Trung bình | Thấp |
| 7 | TLS verification cho CAPAM connection | 🟡 Thấp | Trung bình |

---

## 12. Tuyên bố phạm vi sử dụng

> [!IMPORTANT]
> Công cụ này được thiết kế **chỉ dành cho mục đích hợp pháp**: tự động hóa đăng nhập vào hệ thống CAPAM của chính người dùng trong môi trường doanh nghiệp nội bộ.  
> Việc sử dụng để đăng nhập vào tài khoản người khác mà không có sự cho phép là vi phạm pháp luật và chính sách sử dụng hệ thống.
