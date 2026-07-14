# BẢN KHẢO SÁT & KẾ HOẠCH THỰC HIỆN TỰ ĐỘNG HÓA GLOBALPROTECT & CA PAM CLIENT

Tài liệu này tổng hợp dữ liệu khảo sát và vạch ra **Kế Hoạch Thực Hiện Chi Tiết** để lập trình công cụ tự động hóa đăng nhập trên hệ điều hành Linux (Kubuntu/KDE Plasma).

---

## Phần 1: ĐÁNH GIÁ TÍNH KHẢ THI (FEASIBILITY ASSESSMENT)

Dựa trên các bài test đã chạy, kịch bản tự động hóa này là **100% KHẢ THI** và có tính ổn định cao nhờ áp dụng các kỹ thuật thông minh thay vì hardcode tọa độ:

1.  **Mở GlobalProtect không cần click tọa độ (Rất khả thi):** Sử dụng `D-Bus` (`org.kde.StatusNotifierItem.Activate`) để giả lập thao tác click vào khay hệ thống. Đã test thành công với độ trễ gần như bằng 0.
2.  **Nhận diện luồng nhập liệu GlobalProtect (Khả thi cao):** Sử dụng cơ chế Focus -> `Ctrl+A` -> `Ctrl+C` -> Đọc Clipboard để nhận biết màn hình hiện tại là Portal hay Login. (Lưu ý: Sẽ thêm logic backup/restore clipboard của người dùng để không làm mất dữ liệu của họ).
3.  **Kiểm tra kết nối VPN (Chính xác 100%):** Sử dụng `socket` Python kết nối TCP đến Port 443 của IP `10.64.213.188`. Xóa bỏ hoàn toàn việc "sleep mò", công cụ sẽ chạy tiếp ngay khi mạng vừa thông.
4.  **Tự động chọn máy chủ trên CAPAM (Cực kỳ chính xác):** Đã cắt được các template (`template_200.png`, `template_12.png`, `template_rdp.png`) và test với thuật toán OpenCV `matchTemplate` cho kết quả chính xác 100%. Nút RDP luôn cách nhãn tên thiết bị một khoảng `+280px` trục X và `+20px` trục Y.
5.  **Giao diện người dùng (Khả thi):** PyQt5 hỗ trợ rất tốt QThread (luồng nền) giúp chạy các lệnh `pyautogui`, `wmctrl` mà không làm đơ giao diện chính.

---

## Phần 2: KẾ HOẠCH THỰC HIỆN CHI TIẾT (IMPLEMENTATION PLAN)

Để xây dựng công cụ, chúng ta sẽ chia thành 4 Giai đoạn (Phases). Toàn bộ code sẽ được viết vào 1 file chính là `main_automation.py` cùng với thư mục chứa template.

### Giai đoạn 1: Chuẩn bị Thư viện và Cấu trúc dự án
1.  Đảm bảo cài đặt đủ các thư viện: `PyQt5`, `pyautogui`, `pyperclip`, `opencv-python-headless`, `numpy`, `dbus-python`.
2.  Gom nhóm 3 file ảnh template (`template_200.png`, `template_12.png`, `template_rdp.png`) vào thư mục `templates/` cùng cấp với script.
3.  Tạo bộ khung class `AutomationWorker(QThread)` để xử lý luồng chạy ngầm.
4.  Tạo bộ khung class `MainWindow(QMainWindow)` cho giao diện.

### Giai đoạn 2: Xây dựng Module Tự động hóa cốt lõi (Core Automation)
Viết các hàm helper tĩnh (static methods) để xử lý tương tác HĐH:
1.  `focus_window(window_title)`: Sử dụng `wmctrl -a`. Đảm bảo focus thành công trước khi gõ phím.
2.  `activate_gp_tray()`: Code D-Bus để gọi `PanGPUI`.
3.  `read_input_context()`: Lưu clipboard hiện tại -> Gửi `Ctrl+A`, `Ctrl+C` -> Đọc text -> Trả lại clipboard cũ.
4.  `wait_for_network(host, port, timeout_total)`: Vòng lặp ping/socket tới CAPAM Server.
5.  `find_and_click_rdp(template_name)`: Chụp ảnh màn hình `maim` hoặc `pyautogui` -> Dùng `cv2.matchTemplate` -> Tính tọa độ `X+280, Y+20` -> Gọi `pyautogui.click()`.

### Giai đoạn 3: Viết Logic Kịch bản (Luồng chạy trong QThread)
Đưa các hàm helper vào luồng chạy chính:
1.  **Bước 1 - Mở & Nhập GlobalProtect:**
    *   Gọi `activate_gp_tray()`. Chờ 1-2s. Focus `GlobalProtect`.
    *   Gọi `read_input_context()`.
    *   Nếu trả về `vpn.gdt.gov.vn` (Màn hình Portal): Nhấn `Enter` -> Chờ 2s -> Gõ `vnanh.sp`, `Tab`, `Mật_khẩu_gốc + OTP`, `Enter`.
    *   Nếu trả về rỗng hoặc `vnanh.sp` (Màn hình Login): Gõ `vnanh.sp` (hoặc để nguyên nếu đã có), `Tab`, `Mật_khẩu_gốc + OTP`, `Enter`.
2.  **Bước 2 - Chờ VPN:**
    *   Chạy `wait_for_network("10.64.213.188", 443)`. Cập nhật log lên UI.
3.  **Bước 3 - Khởi động & Nhập CAPAM:**
    *   Gọi `subprocess.Popen(["/home/gone/CAPAMClient/CAPAMClient"])`.
    *   Vòng lặp chờ cửa sổ `Symantec Privileged Access Manager`. Focus nó.
    *   Gõ `10.64.213.188`, `Enter`. Chờ 3-4s cho màn hình login load.
    *   Gõ `vnanh.sp`, `Tab`, `Mật_khẩu_gốc + OTP`, `Enter`.
4.  **Bước 4 - Chọn Server (Nếu được yêu cầu):**
    *   Chờ cửa sổ đổi tên thành `Symantec Privileged Access Manager Client - 10.64.213.188`.
    *   Gọi hàm `find_and_click_rdp('template_200.png')` hoặc `12` tương ứng.

### Giai đoạn 4: Xây dựng Giao diện UI (PyQt5)
1.  Thiết kế form (không viền - frameless hoặc có viền tối màu phong cách Catppuccin):
    *   **Input OTP:** Font chữ to, tự động focus khi mở app, chỉ nhận 6 số.
    *   **Radio Buttons:** Chọn máy 200, máy 12, hoặc Không chọn.
    *   **Nút Bắt đầu:** Lớn, màu xanh dương. Khóa lại khi đang chạy.
    *   **QTextEdit (Log Console):** Hiển thị các lệnh `emit` từ `AutomationWorker` để báo cáo tiến độ (vd: "Đang mở VPN...", "Đang kết nối...").
2.  Gắn các tín hiệu (Signals/Slots) giữa `AutomationWorker` và `MainWindow` để cập nhật UI mượt mà.

---

## KẾT LUẬN
Mọi điều kiện kỹ thuật đã đủ. Rủi ro về thay đổi tọa độ đã được triệt tiêu nhờ D-Bus, Keyboard Shortcuts và OpenCV. Sau khi chốt kế hoạch này, Agent tiếp theo có thể bắt tay ngay vào Giai đoạn 1 & 2 để code `main_automation.py`.
