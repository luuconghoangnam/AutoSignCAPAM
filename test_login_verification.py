import pyautogui
import time
import pyperclip
import subprocess

def main():
    subprocess.run(["wmctrl", "-a", "GlobalProtect"])
    time.sleep(1)
    
    # Click the input field at (1620, 326)
    pyautogui.click(1620, 326)
    time.sleep(0.2)
    
    # Copy content
    pyperclip.copy("")
    pyautogui.hotkey('ctrl', 'a')
    time.sleep(0.1)
    pyautogui.hotkey('ctrl', 'c')
    time.sleep(0.2)
    
    val = pyperclip.paste().strip().lower()
    print(f"Copied value at Y=326: {val!r}")
    
    if "gdt.gov.vn" in val:
        print("RESULT: PORTAL SCREEN DETECTED")
    elif val == "":
        print("RESULT: CREDENTIALS SCREEN DETECTED (Password field is empty)")
    else:
        print(f"RESULT: UNKNOWN CONTENT '{val}'")

if __name__ == '__main__':
    main()
