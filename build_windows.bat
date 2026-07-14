@echo off
echo Dang cai dat cac thu vien can thiet...
pip install -r requirements.txt

echo Dang don dep cac ban build cu...
rmdir /s /q build dist
del /q *.spec

echo Dang dong goi ung dung cho Windows...
pyinstaller --noconsole --onefile ^
    --add-data "template_12.png;templates" ^
    --add-data "template_200.png;templates" ^
    --add-data "template_rdp.png;templates" ^
    --name "CAPAM_AutoSign_Windows" ^
    main_automation.py

echo HOAN TAT! File chay doc lap (.exe) nam trong thu muc: dist\CAPAM_AutoSign_Windows.exe
pause
