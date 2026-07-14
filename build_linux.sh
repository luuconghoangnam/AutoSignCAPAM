#!/bin/bash
echo "Đang cài đặt các thư viện cần thiết (bypass PEP 668)..."
python3 -m pip install --user --break-system-packages -r requirements.txt

echo "Đang dọn dẹp các bản build cũ..."
rm -rf build/ dist/ *.spec

echo "Đang đóng gói ứng dụng cho Linux..."
python3 -m PyInstaller --noconsole --onefile \
    --add-data "template_rdp.png:." \
    --name "CAPAM_AutoSign_Linux" \
    main_automation.py

echo "Đang dọn dẹp các tệp tin tạm (build, spec)..."
rm -rf build/ *.spec

echo "HOÀN TẤT! File chạy độc lập nằm trong thư mục: dist/CAPAM_AutoSign_Linux"
