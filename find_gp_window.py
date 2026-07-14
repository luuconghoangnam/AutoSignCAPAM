import sys
from Xlib import X, display

def get_window_name(win):
    try:
        name = win.get_wm_name()
        if name:
            return name
    except Exception:
        pass
    try:
        prop = win.get_full_property(win.display.intern_atom('_NET_WM_NAME'), 0)
        if prop and prop.value:
            return prop.value.decode('utf-8', errors='ignore')
    except Exception:
        pass
    return None

def get_window_class(win):
    try:
        cls = win.get_wm_class()
        if cls:
            return cls
    except Exception:
        pass
    return None

def scan_windows(win, results):
    name = get_window_name(win)
    cls = get_window_class(win)
    
    if name or cls:
        results.append({
            'id': win.id,
            'name': name,
            'class': cls
        })
        
    try:
        children = win.query_tree().children
        for child in children:
            scan_windows(child, results)
    except Exception:
        pass

def main():
    d = display.Display()
    root = d.screen().root
    results = []
    scan_windows(root, results)
    
    print(f"Found {len(results)} windows:")
    for res in results:
        name_str = res['name']
        cls_str = res['class']
        if name_str or cls_str:
            # Check if any matches GlobalProtect
            is_match = False
            for s in [name_str, str(cls_str)]:
                if s and any(k in s.lower() for k in ['globalprotect', 'gp', 'palo', 'pan']):
                    is_match = True
            if is_match:
                print(f"[*] ID: {hex(res['id'])}, Name: {name_str}, Class: {cls_str}")
            else:
                print(f"    ID: {hex(res['id'])}, Name: {name_str}, Class: {cls_str}")

if __name__ == '__main__':
    main()
