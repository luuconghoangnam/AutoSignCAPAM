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
    --add-data "ui/icon.png:ui" \
    --add-data "ui/radio_unchecked.png:ui" \
    --add-data "ui/radio_checked.png:ui" \
    --add-data "ui/checkbox_unchecked.png:ui" \
    --add-data "ui/checkbox_checked.png:ui" \
    --paths "." \
    --hidden-import "adapters" \
    --hidden-import "adapters.linux" \
    --hidden-import "core.state_machine" \
    --hidden-import "core.gp_handler" \
    --hidden-import "core.capam_handler" \
    --hidden-import "core.rdp_handler" \
    --hidden-import "vision.field_detector" \
    --hidden-import "vision.template_matcher" \
    --hidden-import "ui.main_window" \
    --name "CAPAM_AutoSign_Linux" \
    main.py

echo "Đang dọn dẹp các tệp tin tạm (build, spec)..."
rm -rf build/ *.spec

echo "HOÀN TẤT! File chạy độc lập nằm trong thư mục: dist/CAPAM_AutoSign_Linux"
