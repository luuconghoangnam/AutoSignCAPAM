import dbus

def main():
    bus = dbus.SessionBus()
    try:
        watcher_obj = bus.get_object('org.kde.StatusNotifierWatcher', '/StatusNotifierWatcher')
        watcher = dbus.Interface(watcher_obj, 'org.freedesktop.DBus.Properties')
        items = watcher.Get('org.kde.StatusNotifierWatcher', 'RegisteredStatusNotifierItems')
        
        print(f"Registered items: {items}")
        for item in items:
            print("-" * 40)
            print(f"Item: {item}")
            try:
                # Parse bus name and path
                parts = item.split('/', 1)
                bus_name = parts[0]
                path = '/' + parts[1] if len(parts) > 1 else '/StatusNotifierItem'
                
                # In case bus name starts with colon, it is a unique connection name
                # e.g., :1.56
                item_obj = bus.get_object(bus_name, path)
                props = dbus.Interface(item_obj, 'org.freedesktop.DBus.Properties')
                
                try:
                    item_id = props.Get('org.kde.StatusNotifierItem', 'Id')
                    print(f"  Id: {item_id}")
                except Exception as e:
                    print(f"  Id Error: {e}")
                    
                try:
                    title = props.Get('org.kde.StatusNotifierItem', 'Title')
                    print(f"  Title: {title}")
                except Exception as e:
                    print(f"  Title Error: {e}")
                    
                try:
                    status = props.Get('org.kde.StatusNotifierItem', 'Status')
                    print(f"  Status: {status}")
                except Exception as e:
                    print(f"  Status Error: {e}")
            except Exception as e:
                print(f"  General Error: {e}")
    except Exception as e:
        print(f"Error querying StatusNotifierWatcher: {e}")

if __name__ == '__main__':
    main()
