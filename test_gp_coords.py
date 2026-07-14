import pyautogui
import time
import subprocess

def main():
    print("Focusing GlobalProtect window...")
    subprocess.run(["wmctrl", "-a", "GlobalProtect"])
    time.sleep(1)
    
    # GlobalProtect window is at X=1470, Y=0 (width 300, height 355)
    # Let's test the coordinates:
    
    # 1. Hover over Username box
    print("Hovering over Username field (X=1620, Y=125)...")
    pyautogui.moveTo(1620, 125, duration=1.5)
    time.sleep(1)
    
    # 2. Hover over Password box
    print("Hovering over Password field (X=1620, Y=175)...")
    pyautogui.moveTo(1620, 175, duration=1.5)
    time.sleep(1)
    
    # 3. Hover over Sign In button
    print("Hovering over Sign In button (X=1620, Y=225)...")
    pyautogui.moveTo(1620, 225, duration=1.5)
    time.sleep(1)
    
    print("Done testing!")

if __name__ == '__main__':
    main()
