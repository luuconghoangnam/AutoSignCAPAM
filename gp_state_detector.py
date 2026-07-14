import cv2
import numpy as np
import subprocess
import os

def main():
    display = os.environ.get('DISPLAY', ':0')
    env = {'DISPLAY': display}
    
    # 1. Capture GP window screenshot
    screenshot_path = "/home/gone/NewVolume_200G/repos/ToolsSignCAPAM/gp_window_detect.png"
    print("Capturing GlobalProtect window...")
    subprocess.run(["maim", "-g", "300x400+1470+0", screenshot_path], env=env, check=True)
    
    # 2. Load image and detect fields
    img = cv2.imread(screenshot_path)
    if img is None:
        print("Failed to load image")
        return
        
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(blurred, 50, 150)
    contours, _ = cv2.findContours(edged.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    fields = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        # Input boxes are typically:
        # width: 120 to 290 pixels
        # height: 15 to 45 pixels
        if 120 <= w <= 290 and 15 <= h <= 45:
            fields.append((x, y, w, h))
            
    fields = sorted(fields, key=lambda f: f[1])
    
    print(f"Detected {len(fields)} fields:")
    for idx, (x, y, w, h) in enumerate(fields):
        print(f"  Field {idx}: x={x}, y={y}, w={w}, h={h} (Global: X={1470+x+w//2}, Y={y+h//2})")
        
    if len(fields) == 1:
        print("Result: PORTAL SCREEN")
    elif len(fields) == 2:
        print("Result: CREDENTIALS SCREEN")
    else:
        print("Result: UNKNOWN SCREEN")

if __name__ == '__main__':
    main()
