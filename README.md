# CAPAM Auto-Sign In Tool

Công cụ tự động hóa quy trình đăng nhập **Symantec Privileged Access Manager (CAPAM)** trên Linux và Windows. Thay vì phải nhập thủ công Username, Password + OTP mỗi lần, tool sẽ tự động điền đầy đủ và click đăng nhập chỉ với một thao tác.

## Tính năng

- ✅ Tự động đăng nhập vào CAPAM Client (GlobalProtect + CAPAM)
- ✅ Hỗ trợ nhập OTP (RADIUS) cho bước xác thực 2 yếu tố
- ✅ Nhận diện thông minh cửa sổ CAPAM bằng OpenCV Template Matching
- ✅ Tự động chọn máy đích (RDP) và kết nối ngay không cần thao tác thủ công
- ✅ Tự động điền thông tin vào bảng **Windows Security** sau khi click RDP
- ✅ Giao diện đồ họa PyQt5, tự lưu cài đặt tài khoản
- ✅ Hỗ trợ đa nền tảng: **Linux** (Kubuntu/Ubuntu) và **Windows**

## Yêu cầu hệ thống

### Linux
- Python 3.10+
- `maim` — chụp màn hình (`sudo apt install maim`)
- `wmctrl` — quản lý cửa sổ (`sudo apt install wmctrl`)
- `xdotool` — giả lập bàn phím/chuột (`sudo apt install xdotool`)

### Windows
- Python 3.10+
- Không cần cài thêm gì ngoài các thư viện Python bên dưới

## Cài đặt và chạy từ source

```bash
git clone https://github.com/luuconghoangnam/ToolsSignCAPAM.git
cd ToolsSignCAPAM
pip install -r requirements.txt
python main.py
```

## Đóng gói thành file thực thi

### Linux
```bash
bash build_linux.sh
# Output: dist/CAPAM_AutoSign_Linux
```

### Windows
```bat
build_windows.bat
# Output: dist/CAPAM AutoSign.exe
```

## Cách sử dụng

1. Mở file thực thi (`CAPAM_AutoSign_Linux` hoặc `CAPAM_AutoSign_Windows.exe`)
2. Nhập **Tài khoản** và **Tiền tố Mật khẩu** (phần mật khẩu cố định, không gồm OTP)
3. Chọn **máy đích** muốn kết nối RDP (200 hoặc 12)
4. Mở CAPAM Client sẵn lên
5. Nhập **Mã OTP** (6 chữ số từ ứng dụng xác thực)
6. Nhấn **Tiến hành đăng nhập** → Tool sẽ tự động hoàn tất mọi bước còn lại

## Cấu trúc dự án

```
ToolsSignCAPAM/
├── main.py                # Entry point ứng dụng
├── core/                  # FSM và workflow handlers
├── adapters/              # Tích hợp Windows/Linux
├── vision/                # Nhận diện field/template
├── automation/            # Java Access Bridge tùy chọn
├── ui/                    # Giao diện PyQt5
├── requirements.txt       # Thư viện phụ thuộc Python
├── build_linux.sh         # Script đóng gói cho Linux
├── build_windows.bat      # Script đóng gói cho Windows
├── template_200.png       # Ảnh mẫu nhãn máy 200 (OpenCV template)
├── template_12.png        # Ảnh mẫu nhãn máy 12
└── template_rdp.png       # Ảnh mẫu nút bấm RDP
```

## Lưu ý bảo mật

- Thông tin tài khoản được lưu cục bộ tại `~/.capam_autosign_settings.json`
- Không có thông tin xác thực nào được mã hóa cứng trong source code
- Không gửi bất kỳ dữ liệu nào ra ngoài mạng nội bộ

## Giấy phép

MIT License — Tự do sử dụng, chỉnh sửa và phân phối.
