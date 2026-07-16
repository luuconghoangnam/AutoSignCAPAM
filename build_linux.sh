#!/bin/bash
echo "Đang cài đặt các thư viện cần thiết (bypass PEP 668)..."
python3 -m pip install --user --break-system-packages -r requirements.txt

echo "Đang dọn dẹp các bản build cũ..."
rm -rf build/ dist/ *.spec

echo "Đang đóng gói ứng dụng cho Linux..."
python3 -m PyInstaller --noconsole --onefile \
    --add-data "template_rdp.png:." \
    --add-data "template_200.png:." \
    --add-data "template_12.png:." \
    --add-data "app_icon.png:." \
    --exclude-module PyQt5.QtWebEngine \
    --exclude-module PyQt5.QtWebEngineWidgets \
    --exclude-module PyQt5.QtWebKit \
    --exclude-module PyQt5.QtWebKitWidgets \
    --exclude-module PyQt5.QtQml \
    --exclude-module PyQt5.QtQuick \
    --exclude-module PyQt5.QtSql \
    --exclude-module PyQt5.QtXml \
    --exclude-module PyQt5.QtTest \
    --exclude-module PyQt5.QtSensors \
    --exclude-module PyQt5.QtMultimedia \
    --exclude-module PyQt5.QtMultimediaWidgets \
    --exclude-module PyQt5.QtBluetooth \
    --exclude-module PyQt5.QtLocation \
    --exclude-module PyQt5.QtPositioning \
    --exclude-module PyQt5.QtWebSockets \
    --exclude-module PyQt5.QtDesigner \
    --exclude-module PyQt5.QtHelp \
    --exclude-module PyQt5.QtNetwork \
    --exclude-module scipy \
    --exclude-module pandas \
    --exclude-module matplotlib \
    --exclude-module IPython \
    --exclude-module jinja2 \
    --name "CAPAM AutoSign" \
    main_automation.py

echo "Đang dọn dẹp các tệp tin tạm (build, spec)..."
rm -rf build/ *.spec

echo "HOÀN TẤT! File chạy độc lập nằm trong thư mục: dist/CAPAM AutoSign"

# Hỗ trợ phân vùng NTFS (không gán được quyền thực thi trực tiếp)
echo "Đang sao chép file chạy sang thư mục Home (~/) để cấp quyền thực thi..."
cp "dist/CAPAM AutoSign" "$HOME/CAPAM AutoSign"
chmod +x "$HOME/CAPAM AutoSign"
echo "HOÀN THÀNH! Bạn có thể kích đúp hoặc chạy ứng dụng từ thư mục Home: ~/CAPAM AutoSign"
