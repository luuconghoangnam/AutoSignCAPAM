import cv2
import numpy as np

def main():
    img_path = "/home/gone/NewVolume_200G/repos/ToolsSignCAPAM/gp_window.png"
    img = cv2.imread(img_path)
    if img is None:
        print("Failed to load image")
        return
        
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # We want to find horizontal rectangles that look like input fields.
    # Typically, input fields have a border. Let's do edge detection or thresholding.
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(blurred, 50, 150)
    
    contours, _ = cv2.findContours(edged.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    print(f"Image shape: {img.shape}")
    print("Detected potential input fields:")
    
    fields = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        # Input boxes are typically:
        # width: 150 to 280 pixels (on a 300px wide window)
        # height: 20 to 45 pixels
        if 120 <= w <= 290 and 15 <= h <= 45:
            fields.append((x, y, w, h))
            
    # Sort fields by Y coordinate (top to bottom)
    fields = sorted(fields, key=lambda f: f[1])
    
    for idx, (x, y, w, h) in enumerate(fields):
        print(f"Field {idx}: x={x}, y={y}, w={w}, h={h}")
        # Crop and check average intensity to see if it's light or dark
        crop = gray[y:y+h, x:x+w]
        avg_color = np.mean(crop)
        print(f"  Average intensity: {avg_color:.2f}")

if __name__ == '__main__':
    main()
