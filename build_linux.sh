#!/bin/bash
echo "Đang thiết lập môi trường ảo (venv) để tránh lỗi PEP 668..."
python3 -m venv venv
source venv/bin/activate

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
deactivate
