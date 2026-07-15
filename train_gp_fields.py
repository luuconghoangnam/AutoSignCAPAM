import os
import time
import cv2
import numpy as np
import pygetwindow as gw
from PIL import ImageGrab
import platform

def main():
    print("=== CAPAM AutoSign - GlobalProtect Window Field Training Tool ===")
    
    # 1. Find GlobalProtect window
    windows = gw.getWindowsWithTitle("GlobalProtect")
    if not windows:
        print("[-] GlobalProtect window not found! Make sure GlobalProtect is open and visible on screen.")
        return
        
    win = windows[0]
    print(f"[+] Found window: Title='{win.title}'")
    print(f"    Geometry: Left={win.left}, Top={win.top}, Width={win.width}, Height={win.height}")
    
    # 2. Activate and bring window to front
    try:
        if win.isMinimized:
            win.restore()
        win.activate()
        time.sleep(1.5) # Wait for window to render
    except Exception as e:
        print(f"[-] Cannot activate window: {e}")
        
    # 3. Take screenshot of window
    rect = {"x": win.left, "y": win.top, "w": win.width, "h": win.height}
    bbox = (rect['x'], rect['y'], rect['x'] + rect['w'], rect['y'] + rect['h'])
    screenshot = ImageGrab.grab(bbox=bbox)
    
    img_name = "train_gp_raw.png"
    screenshot.save(img_name)
    print(f"[+] Saved raw window screenshot to: {os.path.abspath(img_name)}")
    
    # 4. Detect input fields using OpenCV
    img = cv2.imread(img_name)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(blurred, 50, 150)
    contours, _ = cv2.findContours(edged.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    print(f"[+] Total raw contours found: {len(contours)}")
    
    labeled_img = img.copy()
    candidates = []
    
    for i, c in enumerate(contours):
        x, y, w, h = cv2.boundingRect(c)
        crop = gray[y:y+h, x:x+w]
        mean_val = np.mean(crop)
        
        # Draw raw contours in red
        cv2.rectangle(labeled_img, (x, y), (x + w, y + h), (0, 0, 180), 1)
        cv2.putText(labeled_img, f"#{i}: {w}x{h}", (x, y - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 0, 180), 1)
        
        # Check coordinates and size conditions
        if 50 <= w <= 400 and 8 <= h <= 60:
            candidates.append({
                "index": i,
                "x": x,
                "y": y,
                "w": w,
                "h": h,
                "mean": mean_val
            })
            
    # Sort fields from top to bottom by Y coordinate
    candidates_sorted = sorted(candidates, key=lambda item: item["y"])
    
    # Save coordinate list to text file
    txt_name = "gp_field_coordinates.txt"
    with open(txt_name, "w", encoding="utf-8") as f:
        f.write("=== GLOBALPROTECT FIELD SURVEY ===\n")
        f.write(f"Window: Left={win.left}, Top={win.top}, Width={win.width}, Height={win.height}\n\n")
        f.write("Potential fields (sorted top to bottom):\n")
        f.write("-" * 80 + "\n")
        f.write(f"{'STT':<5} | {'Contour ID':<10} | {'Relative coords (x, y)':<25} | {'Dimensions (w x h)':<20} | {'Mean Brightness':<10}\n")
        f.write("-" * 80 + "\n")
        
        for stt, cand in enumerate(candidates_sorted):
            f.write(f"{stt:<5} | #{cand['index']:<9} | ({cand['x']:.0f}, {cand['y']:.0f}){'':<13} | {cand['w']}x{cand['h']}{'':<14} | {cand['mean']:.2f}\n")
            
            # Draw green box for matching candidates
            cv2.rectangle(labeled_img, (cand['x'], cand['y']), (cand['x'] + cand['w'], cand['y'] + cand['h']), (0, 255, 0), 2)
            cv2.putText(labeled_img, f"STT {stt} ({cand['w']}x{cand['h']})", (cand['x'] + 5, cand['y'] + 15), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
            
    labeled_img_name = "train_gp_labeled.png"
    cv2.imwrite(labeled_img_name, labeled_img)
    
    print(f"[+] Saved labeled output image to: {os.path.abspath(labeled_img_name)}")
    print(f"[+] Saved coordinate metadata to: {os.path.abspath(txt_name)}")
    print("\n=== SCAN SUMMARY ===")
    if len(candidates_sorted) == 0:
        print("[-] No input fields detected.")
    elif len(candidates_sorted) == 1:
        print("[!] Found 1 field (Portal Screen).")
        print(f"    Field details: {candidates_sorted[0]}")
    else:
        print(f"[+] Found {len(candidates_sorted)} fields (Credentials Screen).")
        for i, c in enumerate(candidates_sorted):
            print(f"    Field {i}: x={c['x']}, y={c['y']}, w={c['w']}, h={c['h']}, mean={c['mean']:.2f}")
            
if __name__ == '__main__':
    main()
