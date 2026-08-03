# -*- mode: python ; coding: utf-8 -*-
"""Spec do PyInstaller — gera o executável Windows (onefile, sem console).

Uso:
    pyinstaller scraper_exe.spec

Gera `dist/GeradorEditais.exe` (ou `dist/GeradorEditais` no Linux/Mac).
"""

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

a = Analysis(
    ["crawler/gui.py"],
    pathex=["."],
    binaries=[],
    datas=[],
    hiddenimports=collect_submodules("crawler"),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["playwright", "pytest", "ruff", "pyinstaller"],
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
    name="GeradorEditais",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # sem janela de terminal
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
