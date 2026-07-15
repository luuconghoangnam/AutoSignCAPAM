import sys
import time
import socket
import subprocess
import cv2
import numpy as np
import pyautogui
import pyperclip
import os
import platform
import shutil
import json
import gc
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QRadioButton, QButtonGroup, QTextEdit, QFrame, QCheckBox)
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QFont, QIcon, QColor, QPalette

def get_resource_path(relative_path):
    """ Lấy đường dẫn tuyệt đối tĩnh (hỗ trợ cả môi trường PyInstaller) """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

class OSAdapter:
    gp_coords_portal = {"x_ratio": 0.5, "y_ratio": 0.79}
    gp_coords_username = {"x_ratio": 0.5, "y_ratio": 0.68}
    gp_coords_password = {"x_ratio": 0.5, "y_ratio": 0.79}
    def focus_window(self, title_keyword, exact=False): pass
    def get_window_rect(self, title_keyword): pass
    def take_screenshot(self, rect, path): pass
    def take_full_screenshot(self, path): pass
    def kill_capam(self): pass
    def launch_capam(self): pass
    def launch_gp_ui(self): pass
    def get_gp_log_path(self): pass

class LinuxAdapter(OSAdapter):
    # Dùng tỷ lệ chính xác từ thực tế (Y=277 và Y=238 trên H=400)
    gp_coords_portal = {"x_ratio": 0.5, "y_ratio": 0.6925}
    gp_coords_username = {"x_ratio": 0.5, "y_ratio": 0.595}
    gp_coords_password = {"x_ratio": 0.5, "y_ratio": 0.6925}
    def focus_window(self, title_keyword, exact=False):
        try:
            if exact:
                subprocess.run(["wmctrl", "-F", "-a", title_keyword], check=False)
            else:
                subprocess.run(["wmctrl", "-a", title_keyword], check=False)
            time.sleep(0.5)
            return True
        except Exception:
            return False
            
    def get_window_rect(self, title_keyword):
        try:
            out = subprocess.check_output(["wmctrl", "-l", "-G"]).decode('utf-8')
            for line in out.splitlines():
                if title_keyword.lower() in line.lower():
                    parts = line.split()
                    if len(parts) >= 6:
                        return {"x": int(parts[2]), "y": int(parts[3]), "w": int(parts[4]), "h": int(parts[5]), "id": parts[0]}
        except Exception:
            pass
        return None
        
    def take_screenshot(self, rect, path):
        display = os.environ.get('DISPLAY', ':0')
        subprocess.run(["maim", "-g", f"{rect['w']}x{rect['h']}+{rect['x']}+{rect['y']}", path], env={'DISPLAY': display}, check=True)
        
    def take_full_screenshot(self, path):
        display = os.environ.get('DISPLAY', ':0')
        subprocess.run(["maim", path], env={'DISPLAY': display}, check=True)
        
    def kill_capam(self):
        subprocess.run(["pkill", "-f", "CAPAMClient"], check=False)
        
    def launch_capam(self):
        subprocess.Popen([os.path.expanduser("~/CAPAMClient/CAPAMClient")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
    def launch_gp_ui(self):
        GP_UI  = "/opt/paloaltonetworks/globalprotect/PanGPUI"
        GP_AGENT = "/opt/paloaltonetworks/globalprotect/PanGPA"

        # ──────────────────────────────────────────────
        # Bước 1: Đảm bảo dịch vụ hệ thống 'gpd' (PanGPS) đang chạy
        # Nếu chưa → dùng pkexec để hiện popup nhập mật khẩu đồ hoạ
        # ──────────────────────────────────────────────
        try:
            res = subprocess.run(["systemctl", "is-active", "gpd"],
                                 capture_output=True, text=True)
            if res.stdout.strip() != "active":
                # pkexec sẽ tự mở KDE Polkit GUI hỏi mật khẩu root
                proc = subprocess.Popen(
                    ["pkexec", "systemctl", "start", "gpd"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                # Chờ tối đa 30 giây để user nhập xong mật khẩu & service khởi động
                for _ in range(30):
                    time.sleep(1)
                    chk = subprocess.run(["systemctl", "is-active", "gpd"],
                                         capture_output=True, text=True)
                    if chk.stdout.strip() == "active":
                        break
        except Exception:
            pass

        # ──────────────────────────────────────────────
        # Bước 2: Đảm bảo user-agent 'gpa' đang chạy
        # ──────────────────────────────────────────────
        try:
            res_gpa = subprocess.run(["systemctl", "--user", "is-active", "gpa"],
                                     capture_output=True, text=True)
            if res_gpa.stdout.strip() != "active":
                if os.path.exists(GP_AGENT):
                    subprocess.Popen([GP_AGENT, "start"],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    subprocess.run(["systemctl", "--user", "start", "gpa"], check=False)
                time.sleep(2)
        except Exception:
            pass

        # ──────────────────────────────────────────────
        # Bước 3: Kích hoạt cửa sổ GlobalProtect
        # Thử qua DBus trước (nếu PanGPUI đã ở system tray), sau đó fallback
        # ──────────────────────────────────────────────
        try:
            import dbus
            bus = dbus.SessionBus()
            watcher_obj = bus.get_object('org.kde.StatusNotifierWatcher',
                                          '/StatusNotifierWatcher')
            watcher = dbus.Interface(watcher_obj, 'org.freedesktop.DBus.Properties')
            items = watcher.Get('org.kde.StatusNotifierWatcher',
                                'RegisteredStatusNotifierItems')
            for item in items:
                parts = item.split('/', 1)
                bus_name = parts[0]
                path = '/' + parts[1] if len(parts) > 1 else '/StatusNotifierItem'
                item_obj = bus.get_object(bus_name, path)
                props = dbus.Interface(item_obj, 'org.freedesktop.DBus.Properties')
                try:
                    if props.Get('org.kde.StatusNotifierItem', 'Id') == 'PanGPUI':
                        notifier = dbus.Interface(item_obj, 'org.kde.StatusNotifierItem')
                        notifier.Activate(0, 0)
                        return True
                except Exception:
                    pass
        except Exception:
            pass

        # Fallback: gọi thẳng PanGPUI với tham số "start from-cli" để cửa sổ hiện ra
        if os.path.exists(GP_UI):
            subprocess.Popen([GP_UI, "start", "from-cli"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen(["globalprotect", "launch-ui"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        return True

    def get_gp_log_path(self):
        return os.path.expanduser("~/.GlobalProtect/PanGPUI.log")

class WindowsAdapter(OSAdapter):
    gp_coords_portal = {"x_ratio": 0.5, "y_ratio": 0.79}
    gp_coords_username = {"x_ratio": 0.5, "y_ratio": 0.68}
    gp_coords_password = {"x_ratio": 0.5, "y_ratio": 0.79}
    def focus_window(self, title_keyword, exact=False):
        try:
            import pygetwindow as gw
            windows = gw.getWindowsWithTitle(title_keyword)
            if windows:
                win = windows[0]
                if win.isMinimized: win.restore()
                win.activate()
                time.sleep(0.5)
                return True
        except Exception:
            pass
        return False
        
    def get_window_rect(self, title_keyword):
        try:
            import pygetwindow as gw
            windows = gw.getWindowsWithTitle(title_keyword)
            if windows:
                win = windows[0]
                return {"x": win.left, "y": win.top, "w": win.width, "h": win.height, "id": "win_id"}
        except Exception:
            pass
        return None
        
    def take_screenshot(self, rect, path):
        from PIL import ImageGrab
        bbox = (rect['x'], rect['y'], rect['x'] + rect['w'], rect['y'] + rect['h'])
        ImageGrab.grab(bbox=bbox).save(path)
        
    def take_full_screenshot(self, path):
        from PIL import ImageGrab
        ImageGrab.grab().save(path)
        
    def kill_capam(self):
        # CREATE_NO_WINDOW flag for windows
        creationflags = 0x08000000 if os.name == 'nt' else 0
        subprocess.run(["taskkill", "/F", "/IM", "CAPAMClient.exe"], check=False, creationflags=creationflags)
        
    def launch_capam(self):
        capam_paths = [
            r"C:\Program Files\Broadcom\CAPAM Client\CAPAMClient.exe",
            r"C:\Program Files (x86)\Broadcom\CAPAM Client\CAPAMClient.exe"
        ]
        launched = False
        for path in capam_paths:
            if os.path.exists(path):
                subprocess.Popen([path])
                launched = True
                break
        if not launched:
            try:
                subprocess.Popen(["CAPAMClient.exe"])
            except:
                pass
                
    def launch_gp_ui(self):
        gp_paths = [
            r"C:\Program Files\Palo Alto Networks\GlobalProtect\PanGPA.exe",
            r"C:\Program Files (x86)\Palo Alto Networks\GlobalProtect\PanGPA.exe"
        ]
        launched = False
        for path in gp_paths:
            if os.path.exists(path):
                subprocess.Popen([path])
                launched = True
                break
        if not launched:
            try:
                subprocess.Popen(["PanGPA.exe"])
            except:
                pass
        return True
        
    def get_gp_log_path(self):
        return os.path.expanduser(r"~\AppData\Local\Palo Alto Networks\GlobalProtect\PanGPA.log")

def get_os_adapter():
    sys_name = platform.system()
    if sys_name == "Windows":
        return WindowsAdapter()
    return LinuxAdapter()

# Cấu hình hằng số
CAPAM_IP_DEFAULT = "10.64.213.188"  # IP mặc định, có thể được ghi đè bởi giá trị nhập trong giao diện

# -- LỚP XỬ LÝ TỰ ĐỘNG HÓA CHẠY NGẦM --
class AutomationWorker(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool)

    def __init__(self, username, password_prefix, otp, server_choice, capam_ip):
        super().__init__()
        self.username = username
        self.password_prefix = password_prefix
        self.otp = otp
        self.server_choice = server_choice  # "200", "12", or "none"
        self.capam_ip = capam_ip
        self.os_tool = get_os_adapter()

    def log(self, message):
        self.log_signal.emit(f"[*] {message}")

    def fill_windows_security_dialog(self):
        """Điền thông tin đăng nhập vào bảng Windows Security sau khi click RDP."""
        WIN_SEC_TITLE = "Windows Security"
        self.log("Đang chờ bảng Windows Security xuất hiện...")
        
        rect = None
        for attempt in range(20):
            rect = self.os_tool.get_window_rect(WIN_SEC_TITLE)
            if rect:
                self.log(f"Đã phát hiện bảng Windows Security sau {attempt} giây.")
                break
            time.sleep(1)
            
        if not rect:
            self.log("Không tìm thấy bảng Windows Security trong 20 giây. Bỏ qua bước này.")
            return False
            
        time.sleep(0.5)
        self.os_tool.focus_window(WIN_SEC_TITLE)
        time.sleep(0.5)
        
        # Chụp ảnh để phát hiện các ô nhập liệu trong bảng Windows Security
        fields = []
        for attempt in range(10):
            fields = self.detect_capam_fields(rect)
            if len(fields) >= 2:
                break
            self.log(f"Đang chờ ô nhập liệu của Windows Security... (Lần {attempt+1}/10)")
            time.sleep(0.5)
            
        self.log(f"Windows Security: Phát hiện thấy {len(fields)} ô nhập liệu.")
        
        if len(fields) < 2:
            self.log("Không đủ ô nhập liệu trong bảng Windows Security.")
            return False
            
        # Ô đầu tiên: User name, ô thứ hai: Password (sắp xếp theo Y từ trên xuống)
        x0, y0, w0, h0 = fields[0]  # User name
        x1, y1, w1, h1 = fields[1]  # Password
        
        # Nhập User name
        click_x0 = rect['x'] + x0 + w0 // 2
        click_y0 = rect['y'] + y0 + h0 // 2
        pyautogui.click(click_x0, click_y0)
        time.sleep(0.15)
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.1)
        pyautogui.write(self.username, interval=0.04)
        self.log(f"Đã nhập User name: {self.username}")
        
        # Nhập Password (password_prefix là mật khẩu đầy đủ ở bước này, không cần OTP)
        click_x1 = rect['x'] + x1 + w1 // 2
        click_y1 = rect['y'] + y1 + h1 // 2
        pyautogui.click(click_x1, click_y1)
        time.sleep(0.15)
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.1)
        pyautogui.write(self.password_prefix, interval=0.04)
        self.log("Đã nhập Password.")
        
        # Nhấn Login bằng Tab + Enter hoặc Enter trực tiếp
        time.sleep(0.3)
        pyautogui.press('enter')
        self.log("Đã nhấn Login — kết nối RDP đang được thiết lập!")
        return True

    def wait_for_network(self, host, port, timeout=30):
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                socket.setdefaulttimeout(1)
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.connect((host, port))
                return True
            except Exception:
                time.sleep(1)
        return False

    def find_and_click_rdp(self):
        screenshot_path = os.path.join(os.environ.get('TEMP', '/tmp'), "capam_full_scr.png")
        
        self.log("Đang chụp ảnh màn hình để tìm nút RDP...")
        try:
            self.os_tool.take_full_screenshot(screenshot_path)
        except Exception as e:
            self.log(f"Lỗi chụp ảnh qua công cụ HĐH, thử fallback pyautogui: {e}")
            pyautogui.screenshot(screenshot_path)
            
        scene = cv2.imread(screenshot_path)
        if os.path.exists(screenshot_path):
            try:
                os.remove(screenshot_path)
            except Exception:
                pass
                
        # Tải ảnh mẫu thiết bị được chọn
        dev_template_name = f"template_{self.server_choice}.png"
        dev_template_path = get_resource_path(dev_template_name)
        dev_template = cv2.imread(dev_template_path)
        
        rdp_template_path = get_resource_path("template_rdp.png")
        rdp_template = cv2.imread(rdp_template_path)
        
        if scene is None or dev_template is None or rdp_template is None:
            self.log(f"Không thể tải ảnh chụp hoặc template cần thiết (Choice: {self.server_choice}).")
            return False
            
        self.log(f"Đang tìm vị trí nhãn thiết bị '{dev_template_name}' trên màn hình...")
        res_dev = cv2.matchTemplate(scene, dev_template, cv2.TM_CCOEFF_NORMED)
        _, max_val_dev, _, max_loc_dev = cv2.minMaxLoc(res_dev)
        
        if max_val_dev < 0.65:
            self.log(f"Không tìm thấy nhãn thiết bị {self.server_choice} (Độ khớp: {max_val_dev:.2f}). Đang chờ...")
            return False
            
        dev_x, dev_y = max_loc_dev
        dev_h, dev_w = dev_template.shape[:2]
        dev_center_y = dev_y + dev_h / 2
        
        self.log(f"Đã tìm thấy thiết bị '{self.server_choice}' tại Y={dev_center_y:.1f}. Đang quét tìm các nút RDP...")
        
        res_rdp = cv2.matchTemplate(scene, rdp_template, cv2.TM_CCOEFF_NORMED)
        threshold = 0.65
        locs_rdp = np.where(res_rdp >= threshold)
        
        rdp_pts = []
        for pt in zip(*locs_rdp[::-1]): # pt is (x, y)
            if not any(abs(pt[1] - existing[0][1]) < 10 and abs(pt[0] - existing[0][0]) < 10 for existing in rdp_pts):
                rdp_pts.append((pt, rdp_template.shape[:2])) # save pt and shape
                
        # Tìm nút RDP có Y-coordinate gần nhất với Y-coordinate của nhãn thiết bị
        best_rdp = None
        min_dist_y = float('inf')
        
        for pt, shape in rdp_pts:
            rdp_h, rdp_w = shape
            rdp_center_y = pt[1] + rdp_h / 2
            dist_y = abs(rdp_center_y - dev_center_y)
            if dist_y < 45 and dist_y < min_dist_y:
                min_dist_y = dist_y
                best_rdp = (pt, shape)
                
        # Giải phóng RAM ngay
        del scene, dev_template, rdp_template, res_dev, res_rdp
        gc.collect()
        
        if best_rdp:
            pt, shape = best_rdp
            rdp_h, rdp_w = shape
            click_x = pt[0] + rdp_w / 2
            click_y = pt[1] + rdp_h / 2
            self.log(f"Đã xác định nút RDP tương thích tại ({click_x}, {click_y}) (Cách dòng chữ thiết bị {min_dist_y:.1f}px)")
            self.log(f"Sắp click kết nối RDP tại tọa độ màn hình ({click_x}, {click_y})")
            pyautogui.click(click_x, click_y)
            return True
        else:
            self.log("Không tìm thấy nút RDP nào nằm cùng dòng với thiết bị đã chọn.")
            return False

    def detect_gp_fields(self, rect):
        screenshot_path = os.path.join(os.environ.get('TEMP', '/tmp'), "gp_crop.png")
        try:
            self.os_tool.take_screenshot(rect, screenshot_path)
        except Exception:
            pass
        
        img = cv2.imread(screenshot_path)
        if os.path.exists(screenshot_path):
            try:
                os.remove(screenshot_path)
            except Exception:
                pass
        if img is None:
            return []
            
        W, H = rect['w'], rect['h']
        min_w = int(0.4 * W)
        max_w = int(0.96 * W)
        min_h = int(0.04 * H)
        max_h = int(0.15 * H)
            
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edged = cv2.Canny(blurred, 50, 150)
        contours, _ = cv2.findContours(edged.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        fields = []
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            # GlobalProtect input field dimensions
            if min_w <= w <= max_w and min_h <= h <= max_h:
                crop = gray[y:y+h, x:x+w]
                mean_val = np.mean(crop)
                # Filter out solid buttons (buttons are dark, text fields are white)
                if mean_val > 180:
                    fields.append((x, y, w, h))
        return sorted(fields, key=lambda f: f[1])

    def detect_capam_fields(self, rect):
        screenshot_path = os.path.join(os.environ.get('TEMP', '/tmp'), "capam_crop.png")
        try:
            self.os_tool.take_screenshot(rect, screenshot_path)
        except Exception:
            pass
        
        img = cv2.imread(screenshot_path)
        if os.path.exists(screenshot_path):
            try:
                os.remove(screenshot_path)
            except Exception:
                pass
        if img is None:
            return []
            
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edged = cv2.Canny(blurred, 50, 150)
        contours, _ = cv2.findContours(edged.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        fields = []
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            # Input field dimensions (covers CAPAM login + Windows Security dialog)
            if 80 <= w <= 280 and 12 <= h <= 40:
                fields.append((x, y, w, h))
        return sorted(fields, key=lambda f: f[1])

    def get_gp_state_from_log(self):
        log_path = self.os_tool.get_gp_log_path()
        if not os.path.exists(log_path):
            return "UNKNOWN"
            
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                f.seek(0, 2)
                size = f.tell()
                f.seek(max(0, size - 150000))
                content = f.read()
            import re
            matches = list(re.finditer(r"RECV_FROM_GPA:\s*(<response>.*?</response>)", content, re.DOTALL))
            if not matches:
                return "UNKNOWN"
            last_msg = matches[-1].group(1)
            if "<type>user_credential</type>" in last_msg:
                return "CREDENTIALS"
            elif "<type>status</type>" in last_msg:
                if "<state>Connected</state>" in last_msg:
                    return "CONNECTED"
                else:
                    return "PORTAL"
        except Exception as e:
            self.log(f"Lỗi đọc trạng thái GP từ file log: {e}")
        return "UNKNOWN"

    def run(self):
        pyautogui.PAUSE = 0.1
        
        # --- BƯỚC 1: KIỂM TRA MẠNG TRƯỚC ---
        self.log(f"Kiểm tra kết nối mạng tới CAPAM ({self.capam_ip})...")
        if self.wait_for_network(self.capam_ip, 443, timeout=5):
            self.log("GlobalProtect đã được kết nối sẵn. Bỏ qua đăng nhập GP.")
        else:
            # --- BƯỚC 2: ĐĂNG NHẬP GLOBALPROTECT ---
            self.log("Bắt đầu kích hoạt GlobalProtect...")
            if not self.os_tool.launch_gp_ui():
                self.log("Không thể khởi động UI của GlobalProtect...")
                
            time.sleep(2.5)
            self.os_tool.focus_window("GlobalProtect", exact=True)
            
            # Thực hiện vòng lặp thử đăng nhập tối đa 5 lần
            gp_success = False
            for attempt in range(1, 6):
                self.log(f"Cố gắng đăng nhập GlobalProtect lần {attempt}...")
                rect = self.os_tool.get_window_rect("GlobalProtect")
                if not rect:
                    self.log("Không tìm thấy cửa sổ GlobalProtect, đang thử lại...")
                    time.sleep(2)
                    continue
                
                # --- Xác định trạng thái màn hình ---
                # Ưu tiên 1: đọc từ file log (nhanh, chính xác)
                state = self.get_gp_state_from_log()
                self.log(f"Trạng thái GlobalProtect từ log: {state}")
                
                if state == "UNKNOWN":
                    # Fallback sang phát hiện bằng OpenCV contours
                    # GP có 3 màn hình:
                    #   PORTAL:      1 ô nhập liệu (nút đã bị loại)
                    #   CREDENTIALS: 2 ô nhập liệu (nút đã bị loại)
                    #   CONFIRM:     0 ô nhập liệu
                    fields = self.detect_gp_fields(rect)
                    num_fields = len(fields)
                    self.log(f"Không đọc được log, phát hiện bằng OpenCV: thấy {num_fields} ô nhập liệu.")
                    if num_fields == 1:
                        state = "PORTAL"
                    elif num_fields == 2:
                        state = "CREDENTIALS"
                    elif num_fields == 0:
                        state = "CONFIRM"
                
                # --- Xử lý từng trạng thái ---
                if state == "PORTAL":
                    # Màn hình Portal: 1 ô nhập URL + 1 nút Connect
                    self.log("Nhận diện: MÀN HÌNH PORTAL GP (1 ô nhập).")
                    fields = self.detect_gp_fields(rect)
                    if len(fields) == 1:
                        fx, fy, fw, fh = fields[0] # Ô đầu tiên là portal url
                        click_x = rect['x'] + fx + fw // 2
                        click_y = rect['y'] + fy + fh // 2
                        self.log(f"Nhấp vào ô Portal theo OpenCV: ({click_x}, {click_y})")
                    else:
                        click_x = rect['x'] + int(rect['w'] * self.os_tool.gp_coords_portal["x_ratio"])
                        click_y = rect['y'] + int(rect['h'] * self.os_tool.gp_coords_portal["y_ratio"])
                        self.log(f"Nhấp vào ô Portal theo tỷ lệ mặc định: ({click_x}, {click_y})")
                    
                    pyautogui.click(click_x, click_y)
                    time.sleep(0.1)
                    pyautogui.hotkey('ctrl', 'a')
                    time.sleep(0.1)
                    pyautogui.press('backspace')
                    time.sleep(0.1)
                    pyautogui.write("vpn.gdt.gov.vn", interval=0.03)
                    time.sleep(0.1)
                    pyautogui.press('enter')
                    self.log("Đã nhập Portal, chờ chuyển trang đăng nhập...")
                    time.sleep(5)
                    self.os_tool.focus_window("GlobalProtect", exact=True)
                    continue
                
                elif state == "CONFIRM":
                    # Màn hình xác nhận: 0 ô nhập liệu, chỉ cần nhấn Enter xác nhận
                    self.log("Nhận diện: MÀN HÌNH XÁC NHẬN GP (0 ô nhập) → nhấn Enter.")
                    pyautogui.press('enter')
                    time.sleep(3)
                    self.os_tool.focus_window("GlobalProtect", exact=True)
                    continue
                    
                elif state == "CREDENTIALS":
                    # Màn hình đăng nhập: 2 ô nhập liệu (username + password)
                    self.log("Nhận diện: MÀN HÌNH ĐĂNG NHẬP GP (2 ô nhập).")
                    fields = self.detect_gp_fields(rect)
                    if len(fields) == 2:
                        # OpenCV tìm được đúng 2 ô → fields[0]=username, fields[1]=password
                        fx0, fy0, fw0, fh0 = fields[0]
                        click_x0 = rect['x'] + fx0 + fw0 // 2
                        click_y0 = rect['y'] + fy0 + fh0 // 2
                        fx1, fy1, fw1, fh1 = fields[1]
                        click_x1 = rect['x'] + fx1 + fw1 // 2
                        click_y1 = rect['y'] + fy1 + fh1 // 2
                        self.log(f"Nhấp vào ô Username/Password theo OpenCV: ({click_x0}, {click_y0}) / ({click_x1}, {click_y1})")
                    else:
                        # Fallback: dùng tỷ lệ phần trăm động theo kích thước cửa sổ thực tế
                        click_x0 = rect['x'] + int(rect['w'] * self.os_tool.gp_coords_username["x_ratio"])
                        click_y0 = rect['y'] + int(rect['h'] * self.os_tool.gp_coords_username["y_ratio"])
                        click_x1 = rect['x'] + int(rect['w'] * self.os_tool.gp_coords_password["x_ratio"])
                        click_y1 = rect['y'] + int(rect['h'] * self.os_tool.gp_coords_password["y_ratio"])
                        self.log(f"Nhấp vào ô Username/Password theo tỷ lệ mặc định: ({click_x0}, {click_y0}) / ({click_x1}, {click_y1})")
                    
                    # Điền Username
                    pyautogui.click(click_x0, click_y0)
                    time.sleep(0.1)
                    pyautogui.hotkey('ctrl', 'a')
                    time.sleep(0.1)
                    pyautogui.press('backspace')
                    time.sleep(0.1)
                    pyautogui.write(self.username, interval=0.03)
                    time.sleep(0.1)
                    
                    # Điền Password + OTP
                    pyautogui.click(click_x1, click_y1)
                    time.sleep(0.1)
                    pyautogui.hotkey('ctrl', 'a')
                    time.sleep(0.1)
                    pyautogui.press('backspace')
                    time.sleep(0.1)
                    pyautogui.write(self.password_prefix + self.otp, interval=0.03)
                    time.sleep(0.1)
                    
                    # Nhấn Đăng nhập
                    self.log("Gửi thông tin đăng nhập GlobalProtect...")
                    pyautogui.press('enter')
                    
                    # Kiểm tra kết nối mạng sau đăng nhập
                    self.log("Đang chờ xác minh kết nối mạng VPN...")
                    if self.wait_for_network(self.capam_ip, 443, timeout=10):
                        gp_success = True
                        break
                    else:
                        self.log("Đăng nhập thất bại hoặc đang tải...")
                        time.sleep(2)
                        
                elif state == "CONNECTED":
                    self.log("GlobalProtect đã được kết nối thành công từ trước.")
                    gp_success = True
                    break
                        
            if not gp_success and not self.wait_for_network(self.capam_ip, 443, timeout=5):
                self.log("Quá thời gian kết nối VPN. Đăng nhập GP thất bại.")
                self.finished_signal.emit(False)
                return
                
            self.log("Đăng nhập GlobalProtect thành công, VPN đã thông!")

        # --- BƯỚC 3: MỞ VÀ ĐĂNG NHẬP CAPAM CLIENT ---

        self.log("Khởi động Broadcom CAPAM Client...")
        # Kiểm tra xem có cửa sổ CAPAM cũ nào đang chạy không, tắt đi trước
        self.os_tool.kill_capam()
        time.sleep(0.5)
        self.os_tool.launch_capam()
        
        # Chờ cửa sổ xuất hiện
        rect_capam = None
        for _ in range(30):
            rect_capam = self.os_tool.get_window_rect("Symantec Privileged Access Manager")
            if rect_capam:
                break
            time.sleep(0.5)
            
        if not rect_capam:
            self.log("Không tìm thấy cửa sổ CAPAM Client.")
            self.finished_signal.emit(False)
            return
            
        time.sleep(1.5) # Chờ ứng dụng render xong
        self.os_tool.focus_window("Symantec Privileged Access Manager")
        
        # --- BƯỚC 3A: NHẬP IP TRÊN MÀN HÌNH ĐẦU TIÊN (ADDRESS) ---
        self.log("Nhập IP máy chủ CAPAM...")
        rect_capam = self.os_tool.get_window_rect("Symantec Privileged Access Manager")
        if not rect_capam:
            self.log("Không tìm thấy cửa sổ CAPAM để nhập IP.")
            self.finished_signal.emit(False)
            return
            
        fields = []
        for attempt in range(15):
            fields = self.detect_capam_fields(rect_capam)
            if len(fields) >= 1:
                break
            self.log(f"Đang chờ ô nhập IP xuất hiện... (Lần {attempt+1}/15)")
            time.sleep(1)
        self.log(f"Màn hình Address: Phát hiện thấy {len(fields)} ô nhập liệu.")
        
        if len(fields) >= 1:
            # Ô đầu tiên luôn là Address (IP)
            x_local, y_local, w_local, h_local = fields[0]
            click_x = rect_capam['x'] + x_local + w_local // 2
            click_y = rect_capam['y'] + y_local + h_local // 2
            
            pyautogui.click(click_x, click_y)
            time.sleep(0.1)
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.1)
            pyautogui.press('backspace')
            time.sleep(0.1)
            pyautogui.write(self.capam_ip, interval=0.03)
            time.sleep(0.1)
            pyautogui.press('enter')
            
            self.log("Đã nhập IP và nhấn Enter, chờ 5 giây tải màn hình đăng nhập...")
            time.sleep(5)
            self.os_tool.focus_window("Symantec Privileged Access Manager")
        else:
            self.log("Không phát hiện được ô nhập IP nào trên CAPAM.")
            self.finished_signal.emit(False)
            return

        # --- BƯỚC 3B: ĐIỀN THÔNG TIN ĐĂNG NHẬP (USER/PASS) ---
        self.log("Điền thông tin đăng nhập CAPAM...")
        rect_capam = self.os_tool.get_window_rect("Symantec Privileged Access Manager")
        if not rect_capam:
            self.log("Không tìm thấy cửa sổ CAPAM để nhập tài khoản.")
            self.finished_signal.emit(False)
            return
            
        fields = []
        for attempt in range(15):
            rect_capam = self.os_tool.get_window_rect("Symantec Privileged Access Manager")
            if rect_capam:
                fields = self.detect_capam_fields(rect_capam)
                if len(fields) >= 2:
                    break
            self.log(f"Đang chờ màn hình đăng nhập hiển thị đủ các ô nhập liệu... (Lần {attempt+1}/15)")
            time.sleep(1)
            
        self.log(f"Màn hình Đăng nhập: Phát hiện thấy {len(fields)} ô nhập liệu.")
        
        if len(fields) >= 2:
            x0, y0, w0, h0 = fields[0] # Username field (Y thấp hơn)
            x1, y1, w1, h1 = fields[1] # Password field (Y cao hơn)
            
            # Username
            click_x0 = rect_capam['x'] + x0 + w0 // 2
            click_y0 = rect_capam['y'] + y0 + h0 // 2
            pyautogui.click(click_x0, click_y0)
            time.sleep(0.1)
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.1)
            pyautogui.press('backspace')
            time.sleep(0.1)
            pyautogui.write(self.username, interval=0.03)
            time.sleep(0.1)
            
            # Password + OTP
            click_x1 = rect_capam['x'] + x1 + w1 // 2
            click_y1 = rect_capam['y'] + y1 + h1 // 2
            pyautogui.click(click_x1, click_y1)
            time.sleep(0.1)
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.1)
            pyautogui.press('backspace')
            time.sleep(0.1)
            pyautogui.write(self.password_prefix + self.otp, interval=0.03)
            time.sleep(0.1)
            
            pyautogui.press('enter')
            self.log("Đã gửi thông tin đăng nhập CAPAM.")
        else:
            self.log("Lỗi: Không tìm thấy đủ 2 ô nhập tài khoản/mật khẩu trên màn hình đăng nhập CAPAM.")
            self.finished_signal.emit(False)
            return
            
        # --- BƯỚC 4: CHỌN MÁY CHỦ ---
        if self.server_choice != "none":
            self.log(f"Đang chờ hiển thị màn hình danh sách thiết bị để chọn máy {self.server_choice}...")
            
            target_title = f"Symantec Privileged Access Manager Client - {self.capam_ip}"
            device_window_rect = None
            
            # Khảo sát danh sách cửa sổ mỗi 0.5s trong tối đa 20 giây
            for i in range(40):
                device_window_rect = self.os_tool.get_window_rect(target_title)
                if device_window_rect:
                    self.log(f"Đã phát hiện màn hình danh sách thiết bị sau {i*0.5:.1f} giây.")
                    break
                time.sleep(0.5)
                
            if not device_window_rect:
                self.log("Quá thời gian: Không tìm thấy cửa sổ danh sách thiết bị CAPAM Client.")
                self.finished_signal.emit(False)
                return
                
            time.sleep(1.5) # Chờ danh sách thiết bị render đầy đủ
            self.log("Đang focus vào cửa sổ danh sách thiết bị...")
            self.os_tool.focus_window(target_title)
            time.sleep(0.5)
            
            self.log("Bắt đầu phân tích thông minh danh sách thiết bị...")
            
            rdp_success = False
            # Nới lỏng thời gian chờ lên 30 giây (30 lần lặp) vì CAPAM đôi khi tải rất chậm
            for match_attempt in range(30): 
                if self.find_and_click_rdp():
                    self.log("Đã click chọn kết nối RDP máy chủ thành công!")
                    rdp_success = True
                    break
                self.log(f"Đang chờ CAPAM load xong các nút RDP... (Lần {match_attempt+1}/30)")
                time.sleep(1)
                
            if not rdp_success:
                self.log("Lỗi: Quá thời gian chờ (30s) mà CAPAM vẫn chưa tải xong danh sách máy.")
                self.finished_signal.emit(False)
                gc.collect()
                return
            
            # --- BƯỚC 5: ĐIỀN THÔNG TIN VÀO BẢNG WINDOWS SECURITY ---
            self.fill_windows_security_dialog()
            
        self.log("==> KỊCH BẢN TỰ ĐỘNG HÓA HOÀN TẤT! <==")
        self.finished_signal.emit(True)
        
        # Dọn dẹp toàn bộ bộ nhớ còn sót lại
        gc.collect()

# -- GIAO DIỆN CHÍNH (PYQT5) --
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
        
    def initUI(self):
        self.settings_file = os.path.expanduser("~/.capam_autosign_settings.json")
        self.setWindowTitle('CAPAM Auto-Sign In Tool (Kubuntu Edition)')
        self.setFixedSize(480, 530)

        self.setStyleSheet("""
            QMainWindow { background-color: #1e1e2e; }
            QLabel { color: #cdd6f4; font-size: 12px; font-weight: bold; }
            QLineEdit {
                background-color: #313244; color: #89b4fa;
                border: 2px solid #45475a; border-radius: 6px;
                padding: 4px 6px; font-size: 13px; font-weight: bold; min-height: 22px;
            }
            QLineEdit#otp_input { font-size: 22px; letter-spacing: 5px; min-height: 36px; }
            QLineEdit:focus { border: 2px solid #89b4fa; }
            QRadioButton { color: #cdd6f4; font-size: 12px; spacing: 6px; }
            QRadioButton::indicator { width: 14px; height: 14px; }
            QPushButton {
                background-color: #89b4fa; color: #1e1e2e;
                font-size: 13px; font-weight: bold; border-radius: 6px; padding: 7px;
            }
            QPushButton:hover { background-color: #b4befe; }
            QPushButton:disabled { background-color: #45475a; color: #a6adc8; }
            QPushButton#btn_cancel { background-color: #f38ba8; color: #1e1e2e; }
            QPushButton#btn_cancel:hover { background-color: #eba0ac; }
            QPushButton#btn_cancel:disabled { background-color: #45475a; color: #a6adc8; }
            QCheckBox { color: #a6adc8; font-size: 12px; }
            QTextEdit {
                background-color: #11111b; color: #a6e3a1;
                border: 1px solid #45475a; border-radius: 4px;
                font-family: 'Monospace'; font-size: 11px;
            }
        """)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(16, 14, 16, 14)

        # --- Hàng 1: Username | Password | IP ---
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        v_user = QVBoxLayout()
        v_user.setSpacing(3)
        v_user.addWidget(QLabel("Tài khoản:"))
        self.txt_username = QLineEdit()
        self.txt_username.setPlaceholderText("username")
        v_user.addWidget(self.txt_username)

        v_pass = QVBoxLayout()
        v_pass.setSpacing(3)
        h_pass_lbl = QHBoxLayout()
        h_pass_lbl.addWidget(QLabel("Mật khẩu:"))
        self.chk_show_pass = QCheckBox("Hiện")
        self.chk_show_pass.stateChanged.connect(self.toggle_password)
        h_pass_lbl.addWidget(self.chk_show_pass)
        h_pass_lbl.addStretch()
        v_pass.addLayout(h_pass_lbl)
        self.txt_pass_prefix = QLineEdit()
        self.txt_pass_prefix.setEchoMode(QLineEdit.Password)
        self.txt_pass_prefix.setPlaceholderText("mật khẩu")
        v_pass.addWidget(self.txt_pass_prefix)

        v_ip = QVBoxLayout()
        v_ip.setSpacing(3)
        v_ip.addWidget(QLabel("IP CAPAM:"))
        self.txt_capam_ip = QLineEdit()
        self.txt_capam_ip.setText(CAPAM_IP_DEFAULT)
        self.txt_capam_ip.setPlaceholderText("10.x.x.x")
        v_ip.addWidget(self.txt_capam_ip)

        row1.addLayout(v_user, 3)
        row1.addLayout(v_pass, 3)
        row1.addLayout(v_ip, 2)
        main_layout.addLayout(row1)

        # --- OTP ---
        main_layout.addWidget(QLabel("Nhập mã OTP (6 chữ số) rồi nhấn Enter:"))
        self.txt_otp = QLineEdit()
        self.txt_otp.setObjectName("otp_input")
        self.txt_otp.setMaxLength(6)
        self.txt_otp.setAlignment(Qt.AlignCenter)
        self.txt_otp.setPlaceholderText("______")
        self.txt_otp.returnPressed.connect(self.start_automation)
        main_layout.addWidget(self.txt_otp)

        # --- Chọn máy ---
        main_layout.addWidget(QLabel("Kết nối máy chủ sau khi đăng nhập:"))
        self.bg_server = QButtonGroup()
        rb_row = QHBoxLayout()
        rb_row.setSpacing(12)
        self.rb_200  = QRadioButton("RDP-211.200")
        self.rb_12   = QRadioButton("Terminal-211.12")
        self.rb_none = QRadioButton("Chỉ đăng nhập")
        self.rb_200.setChecked(True)
        for rb in [self.rb_200, self.rb_12, self.rb_none]:
            self.bg_server.addButton(rb)
            rb_row.addWidget(rb)
        rb_row.addStretch()
        main_layout.addLayout(rb_row)

        # --- Auto-exit ---
        self.chk_auto_exit = QCheckBox("Tự động đóng sau khi đăng nhập thành công")
        self.chk_auto_exit.setChecked(True)
        main_layout.addWidget(self.chk_auto_exit)

        # --- Nút bấm ---
        btn_layout = QHBoxLayout()
        self.btn_run = QPushButton("TIẾN HÀNH ĐĂNG NHẬP")
        self.btn_run.clicked.connect(self.start_automation)
        self.btn_cancel = QPushButton("HỦY")
        self.btn_cancel.setObjectName("btn_cancel")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.cancel_automation)
        btn_layout.addWidget(self.btn_run, 3)
        btn_layout.addWidget(self.btn_cancel, 1)
        main_layout.addLayout(btn_layout)

        # --- Logs ---
        main_layout.addWidget(QLabel("Nhật ký thực thi:"))
        self.txt_logs = QTextEdit()
        self.txt_logs.setReadOnly(True)
        main_layout.addWidget(self.txt_logs)

        self.worker = None
        self.load_settings()

    def toggle_password(self):
        if self.chk_show_pass.isChecked():
            self.txt_pass_prefix.setEchoMode(QLineEdit.Normal)
        else:
            self.txt_pass_prefix.setEchoMode(QLineEdit.Password)

    def load_settings(self):
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "username" in data:
                        self.txt_username.setText(data["username"])
                    if "password_prefix" in data:
                        self.txt_pass_prefix.setText(data["password_prefix"])
                    if "capam_ip" in data:
                        self.txt_capam_ip.setText(data["capam_ip"])
                    if "auto_exit" in data:
                        self.chk_auto_exit.setChecked(data["auto_exit"])
            except Exception:
                pass

    def save_settings(self):
        try:
            data = {
                "username": self.txt_username.text().strip(),
                "password_prefix": self.txt_pass_prefix.text().strip(),
                "capam_ip": self.txt_capam_ip.text().strip(),
                "auto_exit": self.chk_auto_exit.isChecked()
            }
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception:
            pass

    def log(self, text):
        self.txt_logs.append(text)

    def start_automation(self):
        username = self.txt_username.text().strip()
        password_prefix = self.txt_pass_prefix.text().strip()
        otp = self.txt_otp.text().strip()
        
        capam_ip = self.txt_capam_ip.text().strip()
        
        if not username or not password_prefix:
            self.log("[!] Vui lòng nhập đầy đủ Tài khoản và Mật khẩu.")
            return
        
        if not capam_ip:
            self.log("[!] Vui lòng nhập IP máy chủ CAPAM.")
            self.txt_capam_ip.setFocus()
            return

        if len(otp) != 6 or not otp.isdigit():
            self.log("[!] Vui lòng nhập đúng mã OTP 6 số.")
            self.txt_otp.setFocus()
            return

        choice = "none"
        if self.rb_200.isChecked(): choice = "200"
        elif self.rb_12.isChecked(): choice = "12"

        self.btn_run.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.txt_username.setEnabled(False)
        self.txt_pass_prefix.setEnabled(False)
        self.txt_capam_ip.setEnabled(False)
        self.txt_otp.setEnabled(False)
        self.rb_200.setEnabled(False)
        self.rb_12.setEnabled(False)
        self.rb_none.setEnabled(False)
        self.chk_show_pass.setEnabled(False)
        self.chk_auto_exit.setEnabled(False)
        
        self.save_settings()
        
        self.txt_logs.clear()
        self.log("[INFO] Bắt đầu khởi chạy kịch bản tự động hóa...")
        
        # Thu nhỏ cửa sổ UI chính để tránh che khuất cửa sổ CAPAM khi chụp màn hình và click RDP
        self.showMinimized()
        
        self.worker = AutomationWorker(username, password_prefix, otp, choice, capam_ip)
        self.worker.log_signal.connect(self.log)
        self.worker.finished_signal.connect(self.automation_finished)
        self.worker.start()

    def cancel_automation(self):
        if self.worker and self.worker.isRunning():
            self.log("[!] Đang dừng kịch bản tự động hóa theo yêu cầu người dùng...")
            self.worker.terminate()
            self.worker.wait()
            self.log("[!] Đã dừng thành công kịch bản tự động hóa.")
        self.automation_finished(False)

    def automation_finished(self, success=False):
        # Khôi phục lại kích thước cửa sổ chính
        self.showNormal()
        self.raise_()
        self.activateWindow()
        
        if success and self.chk_auto_exit.isChecked():
            self.log("[INFO] Tự động đóng ứng dụng theo cài đặt...")
            QApplication.quit()
            return
            
        self.btn_run.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.txt_username.setEnabled(True)
        self.txt_pass_prefix.setEnabled(True)
        self.txt_capam_ip.setEnabled(True)
        self.txt_otp.setEnabled(True)
        self.txt_otp.clear()
        self.rb_200.setEnabled(True)
        self.rb_12.setEnabled(True)
        self.rb_none.setEnabled(True)
        self.chk_show_pass.setEnabled(True)
        self.chk_auto_exit.setEnabled(True)
        self.txt_otp.setFocus()

# Khởi chạy ứng dụng PyQt5
if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
