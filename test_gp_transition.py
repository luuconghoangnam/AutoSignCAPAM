import cv2
import numpy as np
import subprocess
import time
import pyautogui
import os

def detect_fields():
    screenshot_path = "/home/gone/NewVolume_200G/repos/ToolsSignCAPAM/gp_window_detect.png"
    display = os.environ.get('DISPLAY', ':0')
    env = {'DISPLAY': display}
    subprocess.run(["maim", "-g", "300x400+1470+0", screenshot_path], env=env, check=True)
    
    img = cv2.imread(screenshot_path)
    if img is None:
        return []
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(blurred, 50, 150)
    contours, _ = cv2.findContours(edged.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    fields = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if 120 <= w <= 290 and 15 <= h <= 45:
            fields.append((x, y, w, h))
    return sorted(fields, key=lambda f: f[1])

def main():
    pyautogui.PAUSE = 0.1
    subprocess.run(["wmctrl", "-a", "GlobalProtect"])
    time.sleep(1)
    
    # 1. Click portal field at X=1620, Y=326
    print("Clicking portal field at (1620, 326)...")
    pyautogui.click(1620, 326)
    time.sleep(0.2)
    pyautogui.hotkey('ctrl', 'a')
    time.sleep(0.1)
    pyautogui.press('backspace')
    time.sleep(0.1)
    pyautogui.write("vpn.gdt.gov.vn", interval=0.03)
    time.sleep(0.2)
    print("Pressing Enter to Connect...")
    pyautogui.press('enter')
    
    # Wait for transition
    print("Waiting 5 seconds for Credentials screen to load...")
    time.sleep(5)
    
    # Redetect fields
    fields = detect_fields()
    print(f"After transition, detected {len(fields)} fields:")
    for idx, (x, y, w, h) in enumerate(fields):
        print(f"  Field {idx}: x={x}, y={y}, w={w}, h={h} (Global: X={1470+x+w//2}, Y={y+h//2})")

if __name__ == '__main__':
    main()
