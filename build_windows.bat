@echo off
echo Dang cai dat cac thu vien can thiet...
pip install -r requirements.txt

echo Dang don dep cac ban build cu...
rmdir /s /q build dist
del /q *.spec

python -m PyInstaller --noconsole --onefile ^
    --add-data "template_rdp.png;." ^
    --add-data "template_200.png;." ^
    --add-data "template_12.png;." ^
    --paths "." ^
    --hidden-import "adapters" ^
    --hidden-import "adapters.windows" ^
    --hidden-import "adapters.linux" ^
    --hidden-import "core" ^
    --hidden-import "core.state_machine" ^
    --hidden-import "core.gp_handler" ^
    --hidden-import "core.capam_handler" ^
    --hidden-import "core.rdp_handler" ^
    --hidden-import "vision" ^
    --hidden-import "vision.field_detector" ^
    --hidden-import "vision.template_matcher" ^
    --hidden-import "ui" ^
    --hidden-import "ui.main_window" ^
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
    main.py


echo Dang don dep cac tep tin tam (build, spec)...
rmdir /s /q build
del /q *.spec

echo HOAN TAT! File chay doc lap (.exe) nam trong thu muc: dist\CAPAM_AutoSign_Windows.exe
