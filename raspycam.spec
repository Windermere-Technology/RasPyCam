# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['app/main.py'],
    pathex=['app/core', 'app/utilities'],
    binaries=[('/usr/lib/aarch64-linux-gnu/libpython3.11.so', '.')],
    datas=[('app/core/*', 'core'), ('app/utilities/*', 'utilities')],
    hiddenimports=['uuid', 'picamera2', 'numpy', 'PIL', 'cv2', 'libcamera', 'simplejpeg', 'v4l2'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='raspycam',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='raspycam',
)
