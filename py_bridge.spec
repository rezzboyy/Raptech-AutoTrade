# -*- mode: python ; coding: utf-8 -*-
block_cipher = None

a = Analysis(
    ['py_backend/bridge_server.py'],
    pathex=['py_backend'],
    binaries=[],
    datas=[],
    hiddenimports=[
        'MetaTrader5',
        'pandas',
        'numpy',
        'src.backends.native_backend',
        'src.backends.mcp_backend',
        'src.backends.sim_backend',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'matplotlib', 'torch', 'torchvision', 'torchaudio',
        'tensorboard', 'scipy', 'sympy', 'IPython', 'jupyter', 'notebook',
        'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'sklearn', 'numba', 'cv2',
        'PIL', 'pytest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='py_bridge',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='py_bridge',
)
