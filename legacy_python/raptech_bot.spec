# -*- mode: python ; coding: utf-8 -*-
"""Spesifikasi PyInstaller untuk XAVIQ Trading Engine (mode onedir).

Build:  pyinstaller raptech_bot.spec
Hasil:  dist/XAVIQTradingEngine/XAVIQTradingEngine.exe

Mode onedir dipilih karena paling andal untuk aplikasi PySide6 + QML
(startup lebih cepat & lebih sedikit masalah unpack dibanding onefile).
"""

block_cipher = None

# Bundel folder UI (QML + aset) ke dalam distribusi.
datas = [
    ("ui", "ui"),
]

# Dependensi yang di-import secara dinamis / perlu dipastikan ikut.
hiddenimports = [
    "MetaTrader5",
    "pandas",
    "numpy",
    "dotenv",
    "cryptography",
]


a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Library berat yang terpasang di environment tapi TIDAK dipakai bot.
        # Dikecualikan agar EXE ramping & build cepat.
        "tkinter", "matplotlib", "torch", "torchvision", "torchaudio",
        "tensorboard", "scipy", "sympy", "IPython", "jupyter", "notebook",
        "PyQt5", "PyQt6", "PySide2", "sklearn", "numba", "cv2",
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
    name="XAVIQTradingEngine",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,               # aplikasi GUI, tanpa jendela konsol
    disable_windowed_traceback=False,
    icon="ui/assets/icon.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="XAVIQTradingEngine",
)
