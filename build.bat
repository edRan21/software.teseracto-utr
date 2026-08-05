@echo off
echo Limpiando compilaciones anteriores...
if exist "dist" rmdir /s /q "dist"
pyinstaller --clean TESSERACTO-UTR.spec
del /q "dist\TESSERACTO-UTR.exe"
echo Listo. Solo la carpeta dist\TESSERACTO-UTR permanece.
pause