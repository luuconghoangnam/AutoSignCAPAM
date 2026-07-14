import pyautogui
import time
import subprocess

def main():
    subprocess.run(["wmctrl", "-a", "GlobalProtect"])
    time.sleep(1)
    
    # 1. Click Password field at Y=326
    print("Clicking Password field at (1620, 326)...")
    pyautogui.click(1620, 326)
    time.sleep(0.2)
    
    # 2. Shift+Tab to Username field
    print("Pressing Shift+Tab...")
    pyautogui.hotkey('shift', 'tab')
    time.sleep(0.2)
    
    # 3. Clear and type Username
    print("Typing Username...")
    pyautogui.hotkey('ctrl', 'a')
    time.sleep(0.1)
    pyautogui.press('backspace')
    time.sleep(0.1)
    pyautogui.write("vnanh.sp", interval=0.03)
    time.sleep(0.2)
    
    # 4. Tab to Password field
    print("Pressing Tab...")
    pyautogui.press('tab')
    time.sleep(0.2)
    
    # 5. Clear and type Password + dummy OTP
    print("Typing Password...")
    pyautogui.hotkey('ctrl', 'a')
    time.sleep(0.1)
    pyautogui.press('backspace')
    time.sleep(0.1)
    pyautogui.write("Aa0974702766123456", interval=0.03)
    time.sleep(0.2)
    
    # 6. Press Enter
    print("Pressing Enter...")
    pyautogui.press('enter')
    
    print("Done. Checking logs...")

if __name__ == '__main__':
    main()
