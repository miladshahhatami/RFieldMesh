# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller one-folder specification for the RFieldMesh desktop application."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

PROJECT_ROOT = Path(SPEC).resolve().parents[2]
ENTRY_POINT = PROJECT_ROOT / "packaging" / "pyinstaller" / "gui_entry.py"

datas = collect_data_files("plotly") + copy_metadata("rfieldmesh", recursive=True)
hiddenimports = collect_submodules("plotly")

analysis = Analysis(
    [str(ENTRY_POINT)],
    pathex=[str(PROJECT_ROOT / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(analysis.pure)
executable = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="RFieldMesh",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
collection = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="RFieldMesh",
)
