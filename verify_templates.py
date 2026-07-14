import cv2
import numpy as np

def match(template_name, scene_path):
    scene = cv2.imread(scene_path)
    template = cv2.imread(template_name)
    if scene is None or template is None:
        print(f"Error loading {template_name} or {scene_path}")
        return None
        
    result = cv2.matchTemplate(scene, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
    
    print(f"Match for {template_name}: Max value = {max_val:.4f} at {max_loc}")
    return max_loc, max_val

def main():
    scene_path = "/home/gone/NewVolume_200G/repos/ToolsSignCAPAM/ca_window.png"
    
    match("/home/gone/NewVolume_200G/repos/ToolsSignCAPAM/template_200.png", scene_path)
    match("/home/gone/NewVolume_200G/repos/ToolsSignCAPAM/template_12.png", scene_path)
    match("/home/gone/NewVolume_200G/repos/ToolsSignCAPAM/template_rdp.png", scene_path)

if __name__ == '__main__':
    main()
