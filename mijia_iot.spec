# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Mijia IoT macOS app.
Build with:  pyinstaller mijia_iot.spec
"""

import os
from pathlib import Path

project_root = Path(SPECPATH)

# ── Data files bundled into the app ───────────────────────────────────────────
datas = [
    # (source, destination-inside-bundle)
    (str(project_root / "static"), "static"),
    # main.py is imported directly by launcher.py so PyInstaller compiles it;
    # no need to bundle it as a raw data file.
]

# ── Hidden imports that PyInstaller's static analysis misses ──────────────────
hidden_imports = [
    # uvicorn internals loaded at runtime
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.loops.uvloop",
    "uvicorn.lifespan",
    "uvicorn.lifespan.off",
    "uvicorn.lifespan.on",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.http.httptools_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.protocols.websockets.wsproto_impl",
    "uvicorn.protocols.websockets.websockets_sansio_impl",
    "uvicorn._types",
    # anyio back-ends
    "anyio",
    "anyio._backends._asyncio",
    "anyio._backends._trio",
    # starlette / fastapi dynamic imports
    "starlette.routing",
    "starlette.middleware",
    "starlette.middleware.base",
    "starlette.staticfiles",
    "starlette.responses",
    "starlette.background",
    "fastapi.routing",
    "fastapi.staticfiles",
    "fastapi.responses",
    "fastapi.exceptions",
    "fastapi.middleware",
    # pydantic
    "pydantic",
    "pydantic_core",
    "pydantic.deprecated.class_validators",
    # requests / urllib3
    "requests",
    "urllib3",
    "urllib3.util",
    "urllib3.util.retry",
    "charset_normalizer",
    # mijiaAPI internals
    "mijiaAPI",
    "mijiaAPI.apis",
    "mijiaAPI.devices",
    "mijiaAPI.errors",
    "mijiaAPI.logger",
    "mijiaAPI.miutils",
    "mijiaAPI.version",
    # crypto / yaml / qrcode / pillow used by mijiaAPI
    "Crypto",
    "Crypto.Cipher",
    "Crypto.Cipher.AES",
    "yaml",
    "qrcode",
    "PIL",
    "PIL.Image",
    # misc
    "h11",
    "httptools",
    "websockets",
    "email.mime.text",
    "email.mime.multipart",
]

a = Analysis(
    ["launcher.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Mijia IoT",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # no terminal window — it's a GUI/server app
    icon=str(project_root / "static" / "icon.icns"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Mijia IoT",
)

app = BUNDLE(
    coll,
    name="Mijia IoT.app",
    icon=str(project_root / "static" / "icon.icns"),
    bundle_identifier="com.mijia.iot",
    info_plist={
        "CFBundleDisplayName": "Mijia IoT",
        "CFBundleShortVersionString": "0.1.0",
        "CFBundleVersion": "1",
        "LSMinimumSystemVersion": "11.0",
        "NSHighResolutionCapable": True,
        # Suppress the macOS "app is not optimized for this Mac" warning for
        # any bundled x86_64 libs on Apple Silicon (or vice-versa).
        "LSArchitecturePriority": ["arm64", "x86_64"],
    },
)
