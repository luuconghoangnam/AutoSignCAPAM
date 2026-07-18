@echo off
setlocal
cd /d "%~dp0"

set "VENV_PYTHON=%CD%\.venv\Scripts\python.exe"
set "APP_NAME=CAPAM AutoSign"

echo [1/5] Kiem tra Python 3...
if not exist "%VENV_PYTHON%" (
    where py >nul 2>nul
    if not errorlevel 1 (
        py -3 -m venv ".venv"
    ) else (
        where python >nul 2>nul
        if errorlevel 1 (
            echo [LOI] Khong tim thay Python 3. Cai Python 3.11+ va bat tuy chon Add Python to PATH.
            exit /b 1
        )
        python -m venv ".venv"
    )
    if errorlevel 1 (
        echo [LOI] Khong tao duoc virtual environment .venv.
        exit /b 1
    )
)

echo [2/5] Cai dat dependencies trong .venv...
"%VENV_PYTHON%" -m pip install --upgrade pip
if errorlevel 1 exit /b 1
"%VENV_PYTHON%" -m pip install -r "requirements.txt"
if errorlevel 1 exit /b 1

echo [3/5] Don dep build cu...
if exist "build" rmdir /s /q "build"
if exist "build" (
    echo [LOI] Khong xoa duoc thu muc build. Dong tien trinh dang su dung file va thu lai.
    exit /b 1
)
if exist "dist" rmdir /s /q "dist"
if exist "dist" (
    echo [LOI] Khong xoa duoc thu muc dist. Dong EXE dang chay va thu lai.
    exit /b 1
)
del /q "*.spec" >nul 2>nul

echo [4/5] Dong goi ung dung...
"%VENV_PYTHON%" -m PyInstaller --clean --noconfirm --noconsole --onefile ^
    --add-data "template_rdp.png;." ^
    --add-data "template_200.png;." ^
    --add-data "template_12.png;." ^
    --add-data "ui/icon.png;ui" ^
    --add-data "ui/radio_unchecked.png;ui" ^
    --add-data "ui/radio_checked.png;ui" ^
    --add-data "ui/checkbox_unchecked.png;ui" ^
    --add-data "ui/checkbox_checked.png;ui" ^
    --icon "ui/icon.ico" ^
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
     --hidden-import "capture" ^
     --hidden-import "capture.frame" ^
     --hidden-import "capture.window_capture" ^
     --hidden-import "recognition" ^
     --hidden-import "recognition.geometry" ^
     --hidden-import "automation.java_access_bridge" ^
    --hidden-import "JABWrapper.jab_wrapper" ^
    --hidden-import "JABWrapper.context_tree" ^
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
    --name "%APP_NAME%" ^
    main.py
if errorlevel 1 (
    echo [LOI] PyInstaller build that bai.
    exit /b 1
)

echo [5/5] Don dep file trung gian...
if exist "build" rmdir /s /q "build"
del /q "*.spec" >nul 2>nul

if not exist "dist\%APP_NAME%.exe" (
    echo [LOI] Khong tim thay EXE sau build.
    exit /b 1
)

for %%F in ("dist\%APP_NAME%.exe") do echo [OK] %%~fF - %%~zF bytes
exit /b 0
