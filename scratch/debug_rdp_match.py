import cv2
import numpy as np
import subprocess
import os

def main():
    screenshot_path = "debug_scr.png"
    print("Chụp ảnh màn hình hiện tại bằng maim...")
    subprocess.run(["maim", screenshot_path], check=True)
    
    scene = cv2.imread(screenshot_path)
    template = cv2.imread("template_rdp.png")
    
    if scene is None:
        print("Không thể đọc debug_scr.png")
        return
    if template is None:
        print("Không thể đọc template_rdp.png")
        return
        
    result = cv2.matchTemplate(scene, template, cv2.TM_CCOEFF_NORMED)
    threshold = 0.8
    locations = np.where(result >= threshold)
    
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
    print(f"Max match value: {max_val:.4f} tại {max_loc}")
    
    y_coords = []
    for pt in zip(*locations[::-1]):
        if not any(abs(pt[1] - existing_pt[1]) < 10 for existing_pt in y_coords):
            y_coords.append(pt)
            
    print(f"Số nút RDP tìm thấy với threshold {threshold}: {len(y_coords)}")
    for i, pt in enumerate(y_coords):
        print(f"Nút {i+1}: {pt}")
        
    # Thử quét với threshold thấp hơn nếu không tìm thấy
    if len(y_coords) == 0:
        print("Quét với threshold 0.7...")
        locations = np.where(result >= 0.7)
        y_coords_7 = []
        for pt in zip(*locations[::-1]):
            if not any(abs(pt[1] - existing_pt[1]) < 10 for existing_pt in y_coords_7):
                y_coords_7.append(pt)
        print(f"Số nút RDP tìm thấy với threshold 0.7: {len(y_coords_7)}")
        for i, pt in enumerate(y_coords_7):
            print(f"Nút {i+1}: {pt}")

if __name__ == '__main__':
    main()
