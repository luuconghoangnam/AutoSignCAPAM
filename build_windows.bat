@echo off
echo Dang cai dat cac thu vien can thiet...
pip install -r requirements.txt

echo Dang don dep cac ban build cu...
rmdir /s /q build dist
del /q *.spec

echo Dang dong goi ung dung cho Windows...
pyinstaller --noconsole --onefile ^
    --add-data "template_rdp.png;." ^
    --name "CAPAM_AutoSign_Windows" ^
    main_automation.py

echo Dang don dep cac tep tin tam (build, spec)...
rmdir /s /q build
del /q *.spec

echo HOAN TAT! File chay doc lap (.exe) nam trong thu muc: dist\CAPAM_AutoSign_Windows.exe
pause
