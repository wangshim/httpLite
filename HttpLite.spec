# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:/Users/123/AppData/Roaming/Tencent/Marvis/User/oAN1i2XrBlmiGSnPeHljdH4xqJis/workspace/conv_10af8416780e4fa587b8cf86d063d424/temp/httplite/app.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
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
    a.binaries,
    a.datas,
    [],
    name='HttpLite',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['C:/Users/123/AppData/Roaming/Tencent/Marvis/User/oAN1i2XrBlmiGSnPeHljdH4xqJis/workspace/conv_10af8416780e4fa587b8cf86d063d424/temp/httplite/HttpLite.ico'],
)
