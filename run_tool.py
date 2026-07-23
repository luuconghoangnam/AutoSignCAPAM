import sys
import os
import ctypes

def switch_to_default_desktop():
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    
    # Open "default" desktop
    h_default_desk = user32.OpenDesktopW("default", 0, False, 0x1FF)
    if not h_default_desk:
        print(f"[Desktop Wrapper] Warning: Failed to OpenDesktopW('default'). Error: {kernel32.GetLastError()}")
        return False
        
    # SetThreadDesktop
    if not user32.SetThreadDesktop(h_default_desk):
        print(f"[Desktop Wrapper] Warning: Failed to SetThreadDesktop. Error: {kernel32.GetLastError()}")
        return False
        
    print("[Desktop Wrapper] Successfully switched thread desktop to 'default'.")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_tool.py <module_name> [args...]")
        sys.exit(1)
        
    # Switch desktop first
    switch_to_default_desktop()
    
    # Adjust sys.argv for the target module
    target_module = sys.argv[1]
    sys.argv = sys.argv[1:]
    
    # Import and run the module's main function
    import importlib
    try:
        mod = importlib.import_module(target_module)
        if hasattr(mod, "main"):
            sys.exit(mod.main())
        else:
            print(f"Module {target_module} has no main() function.")
            sys.exit(1)
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)
