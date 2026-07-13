# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['GUI/App.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('Config/*.json', 'Config'),
        ('images/*.png', 'images'),
        ('images/*.jpeg', 'images'),
        ('images/*.ico', 'images'),
    ],
    hiddenimports=[
        'psutil', 'pymodbus', 'passlib', 'apscheduler',
        'pyserial', 'requests', 'schedule'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='TESSERACTO-UTR',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='images/TESERACTO.ico',
)

# ============================================================
# PASO CRÍTICO: COLLECT genera la carpeta de distribución
# con el ejecutable y todos los recursos.
# ============================================================
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='TESSERACTO-UTR',
)