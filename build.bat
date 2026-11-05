@echo off
chcp 65001 >nul
echo [1/2] 패키지 설치
py -m pip install --upgrade pip
py -m pip install -r requirements.txt pyinstaller
echo [2/2] exe 빌드
py -m PyInstaller --noconfirm --onefile --windowed --icon assets\icon.ico --add-data "assets;assets" --name GakgungJeomhwajang jeomhwajang_gui.py
echo.
echo 완료: dist\GakgungJeomhwajang.exe
pause
