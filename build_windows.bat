@echo off
echo Dang cai dat cac thu vien can thiet...
pip install -r requirements.txt

echo Dang don dep cac ban build cu...
rmdir /s /q build dist
del /q *.spec

echo Dang dong goi ung dung cho Windows...
pyinstaller --noconsole --onefile ^
    --add-data "template_rdp.png;." ^
    --exclude-module PyQt5.QtWebEngine ^
    --exclude-module PyQt5.QtWebEngineWidgets ^
    --exclude-module PyQt5.QtWebKit ^
    --exclude-module PyQt5.QtWebKitWidgets ^
    --exclude-module PyQt5.QtQml ^
    --exclude-module PyQt5.QtQuick ^
    --exclude-module PyQt5.QtSql ^
    --exclude-module PyQt5.QtXml ^
    --exclude-module PyQt5.QtTest ^
    --exclude-module PyQt5.QtSensors ^
    --exclude-module PyQt5.QtMultimedia ^
    --exclude-module PyQt5.QtMultimediaWidgets ^
    --exclude-module PyQt5.QtBluetooth ^
    --exclude-module PyQt5.QtLocation ^
    --exclude-module PyQt5.QtPositioning ^
    --exclude-module PyQt5.QtWebSockets ^
    --exclude-module PyQt5.QtDesigner ^
    --exclude-module PyQt5.QtHelp ^
    --exclude-module PyQt5.QtNetwork ^
    --exclude-module scipy ^
    --exclude-module pandas ^
    --exclude-module matplotlib ^
    --exclude-module IPython ^
    --exclude-module jinja2 ^
    --name "CAPAM_AutoSign_Windows" ^
    main_automation.py

echo Dang don dep cac tep tin tam (build, spec)...
rmdir /s /q build
del /q *.spec

echo HOAN TAT! File chay doc lap (.exe) nam trong thu muc: dist\CAPAM_AutoSign_Windows.exe
pause
