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
    def focus_window(self, title_keyword, exact=False): pass
    def get_window_rect(self, title_keyword): pass
    def take_screenshot(self, rect, path): pass
    def take_full_screenshot(self, path): pass
    def kill_capam(self): pass
    def launch_capam(self): pass
    def launch_gp_ui(self): pass
    def get_gp_log_path(self): pass

class LinuxAdapter(OSAdapter):
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
        subprocess.Popen(["/home/gone/CAPAMClient/CAPAMClient"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
    def launch_gp_ui(self):
        try:
            import dbus
            bus = dbus.SessionBus()
            watcher_obj = bus.get_object('org.kde.StatusNotifierWatcher', '/StatusNotifierWatcher')
            watcher = dbus.Interface(watcher_obj, 'org.freedesktop.DBus.Properties')
            items = watcher.Get('org.kde.StatusNotifierWatcher', 'RegisteredStatusNotifierItems')
            for item in items:
                parts = item.split('/', 1)
                bus_name = parts[0]
                path = '/' + parts[1] if len(parts) > 1 else '/StatusNotifierItem'
                item_obj = bus.get_object(bus_name, path)
                props = dbus.Interface(item_obj, 'org.freedesktop.DBus.Properties')
                if props.Get('org.kde.StatusNotifierItem', 'Id') == 'PanGPUI':
                    notifier = dbus.Interface(item_obj, 'org.kde.StatusNotifierItem')
                    notifier.Activate(0, 0)
                    return True
        except Exception:
            pass
        subprocess.run(["globalprotect", "launch-ui"], check=False)
        return True

    def get_gp_log_path(self):
        return os.path.expanduser("~/.GlobalProtect/PanGPUI.log")

class WindowsAdapter(OSAdapter):
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
        capam_path = r"C:\Program Files\Broadcom\CAPAM Client\CAPAMClient.exe"
        if os.path.exists(capam_path):
            subprocess.Popen([capam_path])
        else:
            # Fallback if installed in another location or added to PATH
            try:
                subprocess.Popen(["CAPAMClient.exe"])
            except:
                pass
                
    def launch_gp_ui(self):
        gp_path = r"C:\Program Files\Palo Alto Networks\GlobalProtect\PanGPA.exe"
        if os.path.exists(gp_path):
            subprocess.Popen([gp_path])
        else:
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
CAPAM_IP = "10.64.213.188"

# -- LỚP XỬ LÝ TỰ ĐỘNG HÓA CHẠY NGẦM --
class AutomationWorker(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool)

    def __init__(self, username, password_prefix, otp, server_choice):
        super().__init__()
        self.username = username
        self.password_prefix = password_prefix
        self.otp = otp
        self.server_choice = server_choice # "200", "12", or "none"
        self.os_tool = get_os_adapter()

    def log(self, message):
        self.log_signal.emit(f"[*] {message}")

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

    def find_and_click_rdp(self, template_file):
        screenshot_path = os.path.join(os.environ.get('TEMP', '/tmp'), "capam_full_scr.png")
        
        self.log("Đang chụp ảnh màn hình...")
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
                
        template = cv2.imread(get_resource_path(f"templates/{template_file}"))
        
        if scene is None or template is None:
            self.log(f"Không thể tải ảnh chụp hoặc template {template_file}.")
            return False
            
        self.log(f"Đang thực hiện so khớp ảnh với mẫu {template_file}...")
        result = cv2.matchTemplate(scene, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        
        if max_val > 0.8:
            x, y = max_loc
            click_x = x + 280
            click_y = y + 20
            self.log(f"Đã tìm thấy thiết bị ở tọa độ {max_loc}. Sắp click RDP tại ({click_x}, {click_y})")
            pyautogui.click(click_x, click_y)
            
            # Giải phóng RAM ngay lập tức
            del scene, template, result
            gc.collect()
            
            return True
        else:
            self.log(f"Không tìm thấy thiết bị trên màn hình. Độ chính xác cao nhất: {max_val:.2f}")
            del scene, template, result
            gc.collect()
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
            
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edged = cv2.Canny(blurred, 50, 150)
        contours, _ = cv2.findContours(edged.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        fields = []
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            # GlobalProtect input field dimensions
            if 120 <= w <= 290 and 15 <= h <= 45:
                crop = gray[y:y+h, x:x+w]
                mean_val = np.mean(crop)
                # Filter out solid buttons
                if mean_val > 200:
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
            # CAPAM input field dimensions
            if 100 <= w <= 200 and 12 <= h <= 35:
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
                f.seek(max(0, size - 10000))
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
        self.log(f"Kiểm tra kết nối mạng tới CAPAM ({CAPAM_IP})...")
        if self.wait_for_network(CAPAM_IP, 443, timeout=2):
            self.log("GlobalProtect đã được kết nối sẵn. Bỏ qua đăng nhập GP.")
        else:
            # --- BƯỚC 2: ĐĂNG NHẬP GLOBALPROTECT ---
            self.log("Bắt đầu kích hoạt GlobalProtect...")
            if not self.os_tool.launch_gp_ui():
                self.log("Không thể khởi động UI của GlobalProtect...")
                
            time.sleep(1.5)
            self.os_tool.focus_window("GlobalProtect", exact=True)
            
            # Thực hiện vòng lặp thử đăng nhập tối đa 3 lần
            gp_success = False
            for attempt in range(1, 4):
                self.log(f"Cố gắng đăng nhập GlobalProtect lần {attempt}...")
                rect = self.os_tool.get_window_rect("GlobalProtect")
                if not rect:
                    self.log("Không tìm thấy cửa sổ GlobalProtect, đang thử lại...")
                    time.sleep(1)
                    continue
                
                # Xác định trạng thái màn hình: Ưu tiên dùng file log, nếu không được mới dùng CV
                state = self.get_gp_state_from_log()
                self.log(f"Trạng thái GlobalProtect từ log: {state}")
                
                if state == "UNKNOWN":
                    # Fallback sang phát hiện bằng OpenCV contours
                    fields = self.detect_gp_fields(rect)
                    self.log(f"Không đọc được log, phát hiện bằng OpenCV: thấy {len(fields)} ô nhập liệu.")
                    if len(fields) == 1:
                        state = "PORTAL"
                    elif len(fields) == 2:
                        state = "CREDENTIALS"
                
                if state == "PORTAL":
                    self.log("Nhận diện: MÀN HÌNH PORTAL GP.")
                    # Sử dụng tọa độ tương đối an toàn không đổi: Center X = 150, Center Y = 277
                    click_x = rect['x'] + 150
                    click_y = rect['y'] + 277
                    
                    pyautogui.click(click_x, click_y)
                    time.sleep(0.1)
                    pyautogui.hotkey('ctrl', 'a')
                    time.sleep(0.1)
                    pyautogui.press('backspace')
                    time.sleep(0.1)
                    pyautogui.write("vpn.gdt.gov.vn", interval=0.03)
                    time.sleep(0.1)
                    pyautogui.press('enter')
                    self.log("Đã kết nối Portal, chờ chuyển trang đăng nhập...")
                    time.sleep(5)
                    self.os_tool.focus_window("GlobalProtect", exact=True)
                    continue
                    
                elif state == "CREDENTIALS":
                    self.log("Nhận diện: MÀN HÌNH ĐĂNG NHẬP GP.")
                    
                    # Điền Username: Tọa độ tương đối an toàn Center X = 150, Center Y = 238
                    click_x0 = rect['x'] + 150
                    click_y0 = rect['y'] + 238
                    pyautogui.click(click_x0, click_y0)
                    time.sleep(0.1)
                    pyautogui.hotkey('ctrl', 'a')
                    time.sleep(0.1)
                    pyautogui.press('backspace')
                    time.sleep(0.1)
                    pyautogui.write(self.username, interval=0.03)
                    time.sleep(0.1)
                    
                    # Điền Password + OTP: Tọa độ tương đối an toàn Center X = 150, Center Y = 277
                    click_x1 = rect['x'] + 150
                    click_y1 = rect['y'] + 277
                    pyautogui.click(click_x1, click_y1)
                    time.sleep(0.1)
                    pyautogui.hotkey('ctrl', 'a')
                    time.sleep(0.1)
                    pyautogui.press('backspace')
                    time.sleep(0.1)
                    pyautogui.write(self.password_prefix + self.otp, interval=0.03)
                    time.sleep(0.1)
                    
                    # Đăng nhập
                    self.log("Gửi thông tin đăng nhập GlobalProtect...")
                    pyautogui.press('enter')
                    
                    # Kiểm tra kết nối mạng sau đăng nhập
                    self.log("Đang chờ xác minh kết nối mạng VPN...")
                    if self.wait_for_network(CAPAM_IP, 443, timeout=10):
                        gp_success = True
                        break
                    else:
                        self.log("Đăng nhập thất bại hoặc đang tải...")
                        time.sleep(2)
                elif state == "CONNECTED":
                    self.log("GlobalProtect đã được kết nối thành công từ trước.")
                    gp_success = True
                    break
                        
            if not gp_success and not self.wait_for_network(CAPAM_IP, 443, timeout=5):
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
            
        fields = self.detect_capam_fields(rect_capam)
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
            pyautogui.write(CAPAM_IP, interval=0.03)
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
            
        fields = self.detect_capam_fields(rect_capam)
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
            
            target_title = f"Symantec Privileged Access Manager Client - {CAPAM_IP}"
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
            
            template_name = "template_200.png" if self.server_choice == "200" else "template_12.png"
            self.log(f"Bắt đầu tìm kiếm thiết bị bằng mẫu {template_name}...")
            
            rdp_success = False
            for match_attempt in range(10): # Thử tối đa 10 lần trong 10 giây
                if self.find_and_click_rdp(template_name):
                    self.log("Đã click chọn kết nối RDP máy chủ thành công!")
                    rdp_success = True
                    break
                self.log(f"Chưa tìm thấy mẫu {template_name} trên màn hình. Thử lại sau 1 giây... (Lần {match_attempt+1}/10)")
                time.sleep(1)
                
            if not rdp_success:
                self.log("Lỗi: Quá thời gian chờ (10s) mà không định vị được thiết bị trên màn hình.")
                self.finished_signal.emit(False)
                gc.collect()
                return
            
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
        self.setFixedSize(500, 620)
        
        # Style đậm chất Catppuccin Mocha
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e2e;
            }
            QLabel {
                color: #cdd6f4;
                font-size: 14px;
                font-weight: bold;
            }
            QLineEdit {
                background-color: #313244;
                color: #89b4fa;
                border: 2px solid #45475a;
                border-radius: 8px;
                padding: 6px;
                font-size: 14px;
                font-weight: bold;
                min-height: 25px;
            }
            QLineEdit#otp_input {
                font-size: 24px;
                letter-spacing: 5px;
                min-height: 40px;
            }
            QLineEdit:focus {
                border: 2px solid #89b4fa;
            }
            QRadioButton {
                color: #cdd6f4;
                font-size: 13px;
                spacing: 8px;
            }
            QRadioButton::indicator {
                width: 18px;
                height: 18px;
            }
            QPushButton {
                background-color: #89b4fa;
                color: #1e1e2e;
                font-size: 16px;
                font-weight: bold;
                border-radius: 8px;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #b4befe;
            }
            QPushButton:disabled {
                background-color: #45475a;
                color: #a6adc8;
            }
            QPushButton#btn_cancel {
                background-color: #f38ba8;
                color: #1e1e2e;
            }
            QPushButton#btn_cancel:hover {
                background-color: #eba0ac;
            }
            QPushButton#btn_cancel:disabled {
                background-color: #45475a;
                color: #a6adc8;
            }
            QTextEdit {
                background-color: #11111b;
                color: #a6e3a1;
                border: 1px solid #45475a;
                border-radius: 5px;
                font-family: 'Monospace';
                font-size: 12px;
            }
        """)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # 1. Thông tin tài khoản
        cred_layout = QHBoxLayout()
        v_user = QVBoxLayout()
        v_user.addWidget(QLabel("Tài khoản (Username):"))
        self.txt_username = QLineEdit()
        self.txt_username.setText("vnanh.sp")
        v_user.addWidget(self.txt_username)
        
        v_pass = QVBoxLayout()
        h_pass_head = QHBoxLayout()
        h_pass_head.addWidget(QLabel("Tiền tố Mật khẩu:"))
        self.chk_show_pass = QCheckBox("Hiện")
        self.chk_show_pass.setStyleSheet("QCheckBox { color: #a6adc8; font-size: 12px; }")
        self.chk_show_pass.stateChanged.connect(self.toggle_password)
        h_pass_head.addWidget(self.chk_show_pass)
        h_pass_head.addStretch()
        
        v_pass.addLayout(h_pass_head)
        self.txt_pass_prefix = QLineEdit()
        self.txt_pass_prefix.setEchoMode(QLineEdit.Password)
        self.txt_pass_prefix.setText("Aa0974702766")
        v_pass.addWidget(self.txt_pass_prefix)
        
        cred_layout.addLayout(v_user)
        cred_layout.addLayout(v_pass)
        main_layout.addLayout(cred_layout)

        # 2. OTP Input
        lbl_otp = QLabel("Nhập mã OTP (6 chữ số):")
        lbl_otp.setStyleSheet("margin-top: 5px;")
        main_layout.addWidget(lbl_otp)
        
        self.txt_otp = QLineEdit()
        self.txt_otp.setObjectName("otp_input")
        self.txt_otp.setMaxLength(6)
        self.txt_otp.setAlignment(Qt.AlignCenter)
        self.txt_otp.setPlaceholderText("______")
        main_layout.addWidget(self.txt_otp)

        # 2. Server Selection
        lbl_server = QLabel("Tự động kết nối Máy chủ sau khi Login:")
        lbl_server.setStyleSheet("margin-top: 10px;")
        main_layout.addWidget(lbl_server)
        
        self.bg_server = QButtonGroup()
        
        self.rb_200 = QRadioButton("Máy RDP-211.200")
        self.rb_12 = QRadioButton("Máy Terminal-211.12")
        self.rb_none = QRadioButton("Chỉ đăng nhập, không chọn máy")
        self.rb_200.setChecked(True) # Default
        
        self.bg_server.addButton(self.rb_200)
        self.bg_server.addButton(self.rb_12)
        self.bg_server.addButton(self.rb_none)
        
        main_layout.addWidget(self.rb_200)
        main_layout.addWidget(self.rb_12)
        main_layout.addWidget(self.rb_none)
        
        # 3. Auto Exit Checkbox
        self.chk_auto_exit = QCheckBox("Tự động đóng ứng dụng sau khi Đăng nhập thành công")
        self.chk_auto_exit.setStyleSheet("QCheckBox { margin-top: 5px; margin-bottom: 5px; color: #a6e3a1; font-weight: bold; }")
        self.chk_auto_exit.setChecked(True)
        main_layout.addWidget(self.chk_auto_exit)
        
        # 4. Action Buttons Layout
        btn_layout = QHBoxLayout()
        self.btn_run = QPushButton("TIẾN HÀNH ĐĂNG NHẬP")
        self.btn_run.clicked.connect(self.start_automation)
        
        self.btn_cancel = QPushButton("HỦY ĐĂNG NHẬP")
        self.btn_cancel.setObjectName("btn_cancel")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.cancel_automation)
        
        btn_layout.addWidget(self.btn_run)
        btn_layout.addWidget(self.btn_cancel)
        main_layout.addLayout(btn_layout)
        
        # 4. Logs Area
        lbl_logs = QLabel("Nhật ký thực thi (Logs):")
        lbl_logs.setStyleSheet("margin-top: 10px;")
        main_layout.addWidget(lbl_logs)
        
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
                    if "auto_exit" in data:
                        self.chk_auto_exit.setChecked(data["auto_exit"])
            except Exception:
                pass

    def save_settings(self):
        try:
            data = {
                "username": self.txt_username.text().strip(),
                "password_prefix": self.txt_pass_prefix.text().strip(),
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
        
        if not username or not password_prefix:
            self.log("[!] Vui lòng nhập đầy đủ Tài khoản và Mật khẩu.")
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
        self.txt_otp.setEnabled(False)
        self.rb_200.setEnabled(False)
        self.rb_12.setEnabled(False)
        self.rb_none.setEnabled(False)
        self.chk_show_pass.setEnabled(False)
        self.chk_auto_exit.setEnabled(False)
        
        self.save_settings()
        
        self.txt_logs.clear()
        self.log("[INFO] Bắt đầu khởi chạy kịch bản tự động hóa...")
        
        self.worker = AutomationWorker(username, password_prefix, otp, choice)
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
        if success and self.chk_auto_exit.isChecked():
            self.log("[INFO] Tự động đóng ứng dụng theo cài đặt...")
            QApplication.quit()
            return
            
        self.btn_run.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.txt_username.setEnabled(True)
        self.txt_pass_prefix.setEnabled(True)
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
