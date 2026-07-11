; ============================================================
; TESSERACTO-UTR Installer Script
; Usa Modern UI 2 para un instalador profesional en Windows
; ============================================================

!include "MUI2.nsh"

; --- Configuración general ---
Name "TESSERACTO-UTR"
OutFile "Instalador_TESSERACTO-UTR.exe"
InstallDir "$PROGRAMFILES\TESSERACTO-UTR"
RequestExecutionLevel admin

; --- Iconos del instalador y desinstalador ---
!define MUI_ICON "images\TESERACTO.ico"
!define MUI_UNICON "images\TESERACTO.ico"

; --- Páginas del asistente ---
!insertmacro MUI_PAGE_WELCOME

!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

; --- Páginas del desinstalador ---
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; --- Idioma ---
!insertmacro MUI_LANGUAGE "Spanish"

; ============================================================
; Sección de instalación
; ============================================================
Section "Instalar" SecInstalar

    SetOutPath "$INSTDIR"
    ; Copia recursiva de todo el contenido de dist/TESSERACTO-UTR
    File /r "dist\TESSERACTO-UTR\*.*"

    ; --- Accesos directos ---
    CreateDirectory "$SMPROGRAMS\TESSERACTO-UTR"
    CreateShortCut "$SMPROGRAMS\TESSERACTO-UTR\TESSERACTO-UTR.lnk" "$INSTDIR\TESSERACTO-UTR.exe" "" "$INSTDIR\TESSERACTO-UTR.exe" 0
    CreateShortCut "$DESKTOP\TESSERACTO-UTR.lnk" "$INSTDIR\TESSERACTO-UTR.exe" "" "$INSTDIR\TESSERACTO-UTR.exe" 0

    ; --- Registro para desinstalación ---
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\TESSERACTO-UTR" "DisplayName" "TESSERACTO-UTR"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\TESSERACTO-UTR" "UninstallString" '"$INSTDIR\uninstall.exe"'
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\TESSERACTO-UTR" "Publisher" "Tesseract Labs"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\TESSERACTO-UTR" "DisplayVersion" "2.1"
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\TESSERACTO-UTR" "NoModify" 1
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\TESSERACTO-UTR" "NoRepair" 1

    ; --- Desinstalador ---
    WriteUninstaller "$INSTDIR\uninstall.exe"

SectionEnd

; ============================================================
; Sección de desinstalación
; ============================================================
Section "Uninstall"

    Delete "$DESKTOP\TESSERACTO-UTR.lnk"
    RMDir /r "$SMPROGRAMS\TESSERACTO-UTR"
    RMDir /r "$INSTDIR"
    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\TESSERACTO-UTR"

SectionEnd