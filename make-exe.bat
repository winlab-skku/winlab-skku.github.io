@echo off
REM Builds WInLabAdmin.exe (Windows). Needs Python 3 once; the resulting exe does not.
REM The exe runs admin.py / build.py from this folder, so it only needs rebuilding if
REM launcher.py changes or the tools start using a new library.
cd /d "%~dp0"
python -m pip install --upgrade pyinstaller pillow || goto :err
python -m PyInstaller --onefile --name WInLabAdmin --icon NONE --collect-all PIL --hidden-import admin --hidden-import build launcher.py || goto :err
copy /y dist\WInLabAdmin.exe WInLabAdmin.exe >nul
rmdir /s /q build dist >nul 2>&1
del /q WInLabAdmin.spec >nul 2>&1
echo.
echo Done: WInLabAdmin.exe created in this folder. Double-click it to open the admin page.
pause
exit /b 0
:err
echo.
echo Build failed. Make sure Python 3 is installed and "python" works in a terminal.
pause
exit /b 1
