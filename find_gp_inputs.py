import cv2
import numpy as np

def main():
    img_path = "/home/gone/NewVolume_200G/repos/ToolsSignCAPAM/gp_window.png"
    img = cv2.imread(img_path)
    if img is None:
        print("Failed to load image")
        return
        
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    
    # Let's take the vertical slice in the middle of the window (X = w // 2)
    # and print the intensity values to see the input boxes.
    # Input boxes will have a different intensity compared to the background.
    mid_x = w // 2
    slice_y = gray[:, mid_x]
    
    # Print distinct changes in intensity
    print(f"Window height: {h}, width: {w}")
    print("Vertical profile (Y, Color):")
    
    current_val = slice_y[0]
    segments = []
    start_y = 0
    for y in range(1, h):
        val = slice_y[y]
        if abs(int(val) - int(current_val)) > 5:
            segments.append((start_y, y - 1, current_val))
            start_y = y
            current_val = val
    segments.append((start_y, h - 1, current_val))
    
    for start, end, val in segments:
        length = end - start + 1
        if length > 5:  # Filter out noise
            print(f"Y: {start:3d} -> {end:3d} (len={length:3d}): Color={val}")

if __name__ == '__main__':
    main()
