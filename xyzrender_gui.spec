# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for xyzrender GUI.

Build the standalone exe with:

    python -m PyInstaller xyzrender_gui.spec --clean

The output lands in dist/xyzrender-gui/xyzrender-gui.exe
"""

import sys
from pathlib import Path

# This spec lives in the repo root.  Resolve the source tree from SPECPATH so
# the build does not depend on the current working directory.
_REPO_ROOT = Path(SPECPATH)
_SRC = _REPO_ROOT / "src"

# Bundle the *source* xyzrender (library + gui), not an older copy that may be
# installed into site-packages (the installed one has no `gui` subpackage).
sys.path.insert(0, str(_SRC))

import xyzrender as _xr
import xyzgraph  # noqa: E402  (from the COF env site-packages)
import ase as _ase  # noqa: E402
from PyInstaller.utils.hooks import collect_data_files, collect_submodules  # noqa: E402

# ase.io resolves its format plugins lazily (module __getattr__), so a plain
# "import ase.io" never pulls ase.io.cif into the analysis — opening a CIF in
# the frozen exe died with "no module named ase.io.cif".  Force in every io
# submodule plus the element/symmetry data and the modules the viewer uses.
ASE_HIDDEN = collect_submodules("ase.io") + [
    "ase",
    "ase.data",
    "ase.spacegroup",
    "ase.gui.gui",
    "ase.gui.images",
]
# ase data as real files: spacegroup.dat (CIF symmetry expansion) and the
# collections JSONs.  Modern ase keeps ase/data as pure .py modules (see
# ASE_HIDDEN), so there is nothing to collect there.
_ASE_PKG_DIR = Path(_ase.__file__).parent
ASE_DATA = [
    (_ASE_PKG_DIR / "spacegroup", "ase/spacegroup"),
    (_ASE_PKG_DIR / "collections", "ase/collections"),
]

PRESETS_SRC = str(Path(_xr.__file__).parent / "presets")

# xyzgraph loads its element/bond data at runtime via
# importlib.resources.files("xyzgraph.data") — a dynamic import PyInstaller
# cannot see statically.  Force-include the subpackage and copy its JSON
# data files next to it.
_XYGRAPH_DIR = Path(xyzgraph.__file__).parent
XYZGRAPH_DATA = (_XYGRAPH_DIR / "data", "xyzgraph/data")

block_cipher = None


def _collect_conda_dlls():
    """Bundle the conda DLLs that PyInstaller cannot resolve on its own.

    Conda puts the native libraries of RDKit / matplotlib / PIL into
    <env>/Library/bin, which is NOT on PyInstaller's search path.  Without
    this, the frozen exe fails with "DLL load failed while importing
    rdBase".
    """
    env_bin = Path(sys.prefix) / "Library" / "bin"
    patterns = [
        # RDKit rdBase.pyd pulls in (transitively) every RDKit DLL
        "boost_python*.dll",
        "boost_numpy*.dll",
        "RDKit*.dll",
        # matplotlib (Agg) & numpy
        "qhull_r.dll",
        "freetype.dll",
        # pillow file codecs / color management
        "zlib-ng2.dll",
        "jpeg8.dll",
        "openjp2.dll",
        "tiff.dll",
        "lcms2.dll",
        "libwebp*.dll",
        # misc (cclib / lxml-style optional deps)
        "yaml.dll",
        "libxslt.dll",
        "libexslt.dll",
    ]
    out = []
    for pat in patterns:
        for p in sorted(env_bin.glob(pat)):
            out.append((str(p), "."))
    return out


a = Analysis(
    [str(_SRC / "xyzrender" / "gui" / "main.py")],
    pathex=[str(_SRC)],
    binaries=_collect_conda_dlls(),
    datas=[(PRESETS_SRC, "xyzrender/presets"), XYZGRAPH_DATA, *ASE_DATA],
    hiddenimports=[
        # ase: lazy format dispatch + data + viewer modules
        *ASE_HIDDEN,
        # xyzgraph subpackages referenced dynamically (importlib.resources) or
        # imported at runtime — force them in plus their data files
        "xyzgraph",
        "xyzgraph.data",
        "xyzgraph.nci",
        "xyzgraph.parameters",
        # xyzrender package & submodules
        "xyzrender",
        "xyzrender.api",
        "xyzrender.config",
        "xyzrender.renderer",
        "xyzrender.gif",
        "xyzrender.colors",
        "xyzrender.types",
        "xyzrender.utils",
        "xyzrender.selectors",
        "xyzrender.readers",
        "xyzrender.parsers",
        "xyzrender.measure",
        "xyzrender.stereo",
        "xyzrender.annotations",
        "xyzrender.ensemble",
        "xyzrender.overlay",
        "xyzrender.bond_rules",
        "xyzrender.hull",
        "xyzrender.pore",
        "xyzrender.mo",
        "xyzrender.diffuse",
        "xyzrender.cube",
        "xyzrender.crystal",
        "xyzrender.nci",
        "xyzrender.esp",
        "xyzrender.dens",
        "xyzrender.align",
        "xyzrender.surfaces",
        "xyzrender.mcs",
        "xyzrender.interlock",
        "xyzrender.skeletal",
        "xyzrender.face",
        "xyzrender.contours",
        "xyzrender.merge",
        "xyzrender.inputs",
        "xyzrender.export",
        "xyzrender.viewer",
        "xyzrender.gui",
        "xyzrender.gui.i18n",
        # Third-party deps xyzrender relies on
        "cclib",
        "xyzgraph",
        "graphrc",
        "cairosvg",
        "resvg_py",
        "PIL",
        "networkx",
        "numpy",
        # gif.py imports multiprocessing lazily inside _parallel_render;
        # listing it guarantees PyInstaller bundles the multiprocessing
        # hook + its runtime hook (freeze_support diversion of worker
        # children), without which every Pool child opens a GUI window.
        "multiprocessing",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # unused heavyweight toolkits PyInstaller drags in via dep chains
        "PySide6", "shiboken6", "PyQt5", "PyQt6",
        # optional DB backends, never used by xyzrender
        "MySQLdb", "psycopg2",
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
    name="xyzrender-gui",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="分子.ico",
)

# onedir mode: load everything from the `_internal` folder next to the exe.
# Nothing is ever extracted to %TEMP% at start-up, so the exe can never fail
# with "could not create temporary directory".  Ship the whole
# dist/xyzrender-gui/ folder together.
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="xyzrender-gui",
)
