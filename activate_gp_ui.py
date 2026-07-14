import dbus
import subprocess
import time

def main():
    bus = dbus.SessionBus()
    try:
        watcher_obj = bus.get_object('org.kde.StatusNotifierWatcher', '/StatusNotifierWatcher')
        watcher = dbus.Interface(watcher_obj, 'org.freedesktop.DBus.Properties')
        items = watcher.Get('org.kde.StatusNotifierWatcher', 'RegisteredStatusNotifierItems')
        
        target_item = None
        for item in items:
            parts = item.split('/', 1)
            bus_name = parts[0]
            path = '/' + parts[1] if len(parts) > 1 else '/StatusNotifierItem'
            
            try:
                item_obj = bus.get_object(bus_name, path)
                props = dbus.Interface(item_obj, 'org.freedesktop.DBus.Properties')
                item_id = props.Get('org.kde.StatusNotifierItem', 'Id')
                if item_id == 'PanGPUI':
                    target_item = (bus_name, path)
                    break
            except Exception:
                continue
                
        if target_item:
            print(f"Found PanGPUI at {target_item[0]}{target_item[1]}, activating...")
            # Get the notifier interface
            item_obj = bus.get_object(target_item[0], target_item[1])
            notifier = dbus.Interface(item_obj, 'org.kde.StatusNotifierItem')
            # Call Activate with 0, 0 coordinates
            notifier.Activate(0, 0)
            print("Activated. Waiting for window...")
            time.sleep(2)
            
            # Print current windows containing GP
            out = subprocess.check_output(['wmctrl', '-l', '-G', '-p']).decode('utf-8')
            print("Current windows:")
            print(out)
        else:
            print("PanGPUI tray item not found.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    main()
