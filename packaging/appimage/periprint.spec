# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for PeriPrint. Built via packaging/appimage/build.sh
inside the Docker image defined in this same directory — see
docs/appimage-packaging-guide.md for why PyInstaller (not raw
python-appimage/linuxdeploy-plugin-python) and why each collect_* call
below exists.
"""

import os

from PyInstaller.utils.hooks import collect_all, collect_data_files

ROOT = os.path.abspath(os.path.join(SPECPATH, "..", ".."))  # noqa: F821
SRC = os.path.join(ROOT, "src")

datas = []
binaries = []
hiddenimports = []

# customtkinter ships its themes/fonts as package data (JSON/TTF); without
# this the frozen app starts with a blank/broken UI, not an import error.
datas += collect_data_files("customtkinter")

# tkinterdnd2 bundles a prebuilt native tkdnd shared library + Tcl package
# files as package data, not just .py — plain Analysis() won't find these.
# pymupdf/fitz is a compiled extension with its own data files. Both are
# collected defensively; a missing one degrades to an ImportError at
# runtime for that specific feature, not a build failure.
for _pkg in ("tkinterdnd2", "pymupdf", "fitz"):
    try:
        _d, _b, _h = collect_all(_pkg)
    except Exception:
        continue
    datas += _d
    binaries += _b
    hiddenimports += _h

block_cipher = None

a = Analysis(  # noqa: F821
    [os.path.join(SRC, "periprint", "app.py")],
    pathex=[SRC],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # `peripage` (and transitively PyBluez's `bluetooth` module) is
    # deliberately NOT bundled — it's loaded from the system's
    # apt-installed python3-bluez at runtime instead (see
    # infra/peripage_client.py::_default_printer_factory and
    # docs/BLUETOOTH_SETUP.md). The build venv shouldn't have the
    # `bluetooth` extra installed at all, but exclude explicitly too in
    # case it is.
    excludes=["peripage", "bluetooth"],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, cipher=block_cipher)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="periprint",
    debug=False,
    strip=False,
    upx=False,
    console=False,
)

coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="periprint",
)
