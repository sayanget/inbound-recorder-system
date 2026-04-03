@echo off
echo ----------------------------------------
echo   Building Inbound Recorder EXE
echo ----------------------------------------

REM Step 1: Install required packages
python -m pip install --upgrade pip
python -m pip install flask pyinstaller

REM Step 2: Build EXE (single file)
python -m PyInstaller --onefile --add-data "static;static" single_app.py

echo ----------------------------------------
echo Build completed!
echo EXE is in the "dist" folder.
echo ----------------------------------------
pause
