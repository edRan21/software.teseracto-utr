@echo off
pyinstaller --clean TESSERACTO-UTR.spec
del /q "dist\TESSERACTO-UTR.exe"
echo Listo. Solo la carpeta dist\TESSERACTO-UTR permanece.
pause