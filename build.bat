@echo off
chcp 65001 >nul
echo ==========================================
echo   📈 주식 알리미 - .exe 빌드 스크립트
echo ==========================================
echo.

REM Python 설치 확인
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python이 설치되어 있지 않습니다!
    echo    https://www.python.org/downloads/ 에서 설치해주세요.
    echo    설치 시 "Add Python to PATH" 반드시 체크!
    pause
    exit /b 1
)

echo ✅ Python 확인 완료
python --version
echo.

REM PyInstaller 설치
echo 📦 PyInstaller 설치 중...
pip install pyinstaller --quiet
if errorlevel 1 (
    echo ❌ PyInstaller 설치 실패
    pause
    exit /b 1
)
echo ✅ PyInstaller 설치 완료
echo.

REM .exe 빌드
echo 🔨 .exe 빌드 시작...
pyinstaller --onefile --noconsole --name StockWidget stock_widget.py
if errorlevel 1 (
    echo ❌ 빌드 실패
    pause
    exit /b 1
)

echo.
echo ==========================================
echo ✅ 빌드 완료!
echo.
echo    실행파일 위치: dist\StockWidget.exe
echo    이 파일을 바탕화면에 복사해서 사용하세요.
echo ==========================================
echo.

REM 빌드 결과물 열기
explorer dist
pause
