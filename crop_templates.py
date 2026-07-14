import cv2
import numpy as np

def main():
    img_path = "/home/gone/NewVolume_200G/repos/ToolsSignCAPAM/ca_window.png"
    img = cv2.imread(img_path)
    if img is None:
        print("Failed to load image")
        return
        
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Let's save a template for the RDP button.
    # Looking at the user's screenshot, the RDP button has an icon with a monitor and a curved arrow,
    # and the text "RDP" with a dropdown arrow next to it.
    # Let's write a script to crop a few regions where we expect these rows.
    # The window size is 1142x868.
    # The table "Access Devices" starts around Y=200.
    # Row 1 (DRM-RDS02...) is around Y=240.
    # Row 2 (RDP-211.200) is around Y=310.
    # Row 3 (Terminal-211.12) is around Y=380.
    # Let's write a crop script to extract these regions and verify they contain what we need.
    
    # We will crop three templates:
    # 1. RDP button template (from Row 2)
    # 2. RDP-211.200 text template
    # 3. Terminal-211.12 text template
    
    # Let's do some test crops around the expected regions:
    # Column 1 (Device Name) is at the left side, X=10 to X=150.
    # Column 4 (Access Methods) RDP button is around X=260 to X=320.
    
    # We will save these crops:
    # Row 2 Device Name: X=10 to 150, Y=300 to 340
    device_200_crop = img[300:340, 10:150]
    cv2.imwrite("/home/gone/NewVolume_200G/repos/ToolsSignCAPAM/template_200.png", device_200_crop)
    
    # Row 3 Device Name: X=10 to 150, Y=370 to 410
    device_12_crop = img[370:410, 10:150]
    cv2.imwrite("/home/gone/NewVolume_200G/repos/ToolsSignCAPAM/template_12.png", device_12_crop)
    
    # RDP Button on Row 2: X=250 to 330, Y=300 to 340
    rdp_button_crop = img[300:340, 250:330]
    cv2.imwrite("/home/gone/NewVolume_200G/repos/ToolsSignCAPAM/template_rdp.png", rdp_button_crop)
    
    print("Crops saved successfully!")

if __name__ == '__main__':
    main()
