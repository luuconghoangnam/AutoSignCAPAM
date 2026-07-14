import pyautogui
import os
import sys

def main():
    display = os.environ.get('DISPLAY')
    print(f"Current DISPLAY: {display}")
    
    # Ensure DISPLAY is set (default to :0 if not set)
    if not display:
        os.environ['DISPLAY'] = ':0'
        print("Set DISPLAY to :0")
        
    try:
        screenshot_path = "/home/gone/NewVolume_200G/repos/ToolsSignCAPAM/screenshot.png"
        print("Taking screenshot...")
        screenshot = pyautogui.screenshot()
        screenshot.save(screenshot_path)
        print(f"Screenshot saved to {screenshot_path}")
    except Exception as e:
        print(f"Error taking screenshot: {e}", file=sys.stderr)

if __name__ == '__main__':
    main()
