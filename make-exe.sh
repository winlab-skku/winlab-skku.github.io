#!/bin/sh
# macOS / Linux equivalent of make-exe.bat (produces ./admin for that OS)
cd "$(dirname "$0")"
python3 -m pip install --upgrade pyinstaller pillow
python3 -m PyInstaller --onefile --name WInLabAdmin --collect-all PIL --hidden-import build admin.py && cp dist/WInLabAdmin ./WInLabAdmin && rm -rf build dist WInLabAdmin.spec
echo "Done: ./WInLabAdmin"
