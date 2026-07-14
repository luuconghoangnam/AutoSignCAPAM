#!/bin/bash
echo "Đang cài đặt các thư viện cần thiết..."
pip install -r requirements.txt

echo "Đang dọn dẹp các bản build cũ..."
rm -rf build/ dist/ *.spec

echo "Đang đóng gói ứng dụng cho Linux..."
pyinstaller --noconsole --onefile \
    --add-data "template_12.png:templates" \
    --add-data "template_200.png:templates" \
    --add-data "template_rdp.png:templates" \
    --name "CAPAM_AutoSign_Linux" \
    main_automation.py

echo "HOÀN TẤT! File chạy độc lập nằm trong thư mục: dist/CAPAM_AutoSign_Linux"
