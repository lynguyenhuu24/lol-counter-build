@echo off
REM Đóng gói thành file .exe (Windows). Cần: python + pip install pyinstaller
cd /d "%~dp0"
python -m pip install --quiet pyinstaller || goto :err
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name LoLCounterBuild ^
  --add-data "data/champions.json;data" ^
  --add-data "data/items.json;data" ^
  --add-data "data/meta.json;data" ^
  --add-data "data/queues.json;data" ^
  --add-data "data/builds.json;data" ^
  --add-data "data/augments.json;data" ^
  --hidden-import lcbuild.selftest ^
  --hidden-import lcbuild.fetch_data ^
  --hidden-import lcbuild.fetch_builds ^
  --hidden-import lcbuild.fetch_augments ^
  --exclude-module PIL ^
  --exclude-module numpy ^
  launcher.py || goto :err
echo.
echo Xong. File chay duoc: dist\LoLCounterBuild.exe
goto :eof
:err
echo.
echo Dong goi that bai. Xem loi o tren.
exit /b 1
