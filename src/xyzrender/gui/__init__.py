"""xyzrender GUI — full-featured graphical front-end for xyzrender.

Build a standalone exe with:

    python -m PyInstaller xyzrender_gui.spec --noconsole

or run directly:

    python -m xyzrender.gui.main
"""

from xyzrender.gui.main import main

__all__ = ["main"]
