import cv2

def main():
    img_path = "/home/gone/NewVolume_200G/repos/ToolsSignCAPAM/gp_window.png"
    img = cv2.imread(img_path)
    if img is None:
        print("Failed to load image")
        return
        
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    edged = cv2.Canny(blurred, 30, 200)
    contours, _ = cv2.findContours(edged.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    
    print(f"Total contours: {len(contours)}")
    boxes = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if w > 40 and h > 10:
            boxes.append((x, y, w, h))
            
    # Remove duplicate/very close bounding boxes
    unique_boxes = []
    for b in sorted(boxes, key=lambda b: (b[1], b[0])):
        if not any(abs(b[0]-ub[0]) < 5 and abs(b[1]-ub[1]) < 5 and abs(b[2]-ub[2]) < 5 and abs(b[3]-ub[3]) < 5 for ub in unique_boxes):
            unique_boxes.append(b)
            
    for idx, (x, y, w, h) in enumerate(unique_boxes):
        print(f"Box {idx}: x={x}, y={y}, w={w}, h={h}")

if __name__ == '__main__':
    main()
