@echo off
REM Builds admin.exe (Windows). Needs Python 3 once; the resulting exe does not.
REM Run this file by double-clicking it in the website folder.
cd /d "%~dp0"
python -m pip install --upgrade pyinstaller pillow || goto :err
python -m PyInstaller --onefile --name WInLabAdmin --icon NONE --collect-all PIL --hidden-import build admin.py || goto :err
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
