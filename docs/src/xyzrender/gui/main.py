"""xyzrender GUI — VESTA-style full-featured front-end ( bilingual EN/zh ).

Layout (VESTA-inspired):

  +-----------------------------------------------------------+
  | MenuBar                                                   |
  +---------+-------------------------------------------------+
  |  Icons  | Toolbar (lang, open, render, save, open out)    |
  | (left)  +-------------------------------------------------+
  |         |                                                 |
  | Params  |   CENTRE PREVIEW (large, unobstructed)         |
  | Panel   |   (SVG/PNG image + scrollbars)                 |
  | Basic/  |                                                 |
  | Styling/|                                                 |
  | Display/|                                                 |
  | ...     |                                                 |
  |         +-------------------------------------------------+
  |         | Log / console (bottom strip)                    |
  +---------+-------------------------------------------------+
  | Status bar  | Render | Save | Open output | Progress      |
  +-----------------------------------------------------------+

Render only produces a preview (no file is written).  Click Save to write
the result to disk.
"""

from __future__ import annotations

import os
import queue
import sys
import threading
import webbrowser
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from typing import Optional

try:
    from PIL import Image, ImageTk
    _PIL_OK = True
except Exception:  # pragma: no cover
    _PIL_OK = False

# Make sure the local src layout is importable when run as a script.
_HERE = Path(__file__).resolve().parent.parent  # .../xyzrender
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))

import xyzrender  # noqa: E402
from xyzrender import api  # noqa: E402
from xyzrender.gui.i18n import _, set_lang, get_lang, LANGUAGES  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

APP_TITLE_EN = f"xyzrender GUI v{xyzrender.__version__}"
APP_TITLE_ZH = f"xyzrender GUI v{xyzrender.__version__}"

# ---------------------------------------------------------------------------
# Author / contact details (shown in Help ▸ About)
# ---------------------------------------------------------------------------
AUTHOR_NAME = "Shanyue Wei"
AUTHOR_POSTAL = "361021"
AUTHOR_EMAIL = "xmweishanyue@fjirsm.ac.cn"

# ---------------------------------------------------------------------------
# Upstream project this GUI is built on (shown in Help ▸ About)
# ---------------------------------------------------------------------------
PROJECT_URL = "https://github.com/aligfellow/xyzrender"
PROJECT_AUTHOR = "Alister S. Goodfellow"
PROJECT_CITATION = (
    "Goodfellow, A. S.; Nguyen, B. N. Graph-Based Internal Coordinate "
    "Analysis for Transition State Characterization. "
    "J. Chem. Theory Comput. 2026, DOI: 10.1021/acs.jctc.5c02073"
)
PROJECT_DOI = "10.1021/acs.jctc.5c02073"

# ---------------------------------------------------------------------------
# Colour palette (modern flat look)
# ---------------------------------------------------------------------------
BG = "#f2f4f8"          # window / gap background
CARD = "#ffffff"        # panels, cards, input fields
BORDER = "#d8dee7"      # subtle borders
TEXT = "#1f2937"        # primary text
MUTED = "#7b8494"       # secondary text
ACCENT = "#2f6fed"      # primary action colour (Render, links)
ACCENT_DK = "#1f56c9"   # accent hover / pressed
SELECT_BG = "#dbe7ff"   # selection highlight
BAR_BG = "#e7ebf2"      # status bar background
TOOL_BG = "#e4e8ef"     # toolbar / heading strips

PRESETS = [
    "default", "flat", "paton", "skeletal", "bubble", "tube",
    "mtube", "wire", "graph", "pmol", "vdw", "btube",
]

OUTPUT_FORMATS = ["svg", "png", "pdf", "tif", "tiff"]

ROTATION_AXES = ["x", "y", "z", "xy", "xz", "yz", "xyz", "111", "1-11", "11-1"]
SURFACE_STYLES = ["solid", "mesh", "contour", "dot"]
NCI_MODES = ["avg", "pixel", "uniform"]
STEREO_CLASSES = ["point", "ez", "axis", "plane", "helix"]

INPUT_EXTENSIONS = (
    "Molecular files", "*.xyz *.mol *.sdf *.mol2 *.pdb *.smi *.cif "
    "*.cube *.cub *.com *.gjf *.inp *.nw *.vasp POSCAR *.in *.out *.log"
)
ALL_FILES = ("All files", "*.*")

PREVIEW_MAX = 1200  # max preview width/height in px

# Widths (chars) for Entry / Combobox controls inside label frames.
ENTRY_W = 22
SHORT_W = 8
TINY_W = 6
BROWSE_W = 10

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pf(value, cast=float, default=None):
    try:
        return cast((value or "").strip())
    except (ValueError, AttributeError):
        return default


def _pint(value: str, default=None):
    return _pf(value, int, default)


def _pfloat(value: str, default=None):
    return _pf(value, float, default)


def _pbool(value: str):
    if isinstance(value, bool):
        return value
    v = (value or "").strip().lower()
    if v in ("true", "1", "yes", "on"):
        return True
    if v in ("false", "0", "no", "off"):
        return False
    return None


def _gif_active(p: dict) -> bool:
    """True when any GIF animation mode is enabled in *p*."""
    return any(bool(p.get(k)) for k in ("gif_rot", "gif_bounce", "gif_trj", "gif_ts", "gif_diffuse"))


def _gif_kwargs(p: dict) -> dict:
    """Translate the GUI's GIF checkboxes into render_gif() keyword args.

    Rotation / bounce may be combined with TS vibration (matching the CLI's
    ``--gif-rot --gif-ts`` / ``--gif-bounce --gif-ts``).
    """
    wants_rot = bool(p.get("gif_rot"))
    wants_bounce = bool(p.get("gif_bounce"))
    wants_trj = bool(p.get("gif_trj"))
    wants_ts = bool(p.get("gif_ts"))
    wants_diffuse = bool(p.get("gif_diffuse"))

    if not (wants_rot or wants_bounce or wants_trj or wants_ts or wants_diffuse):
        return {}

    kw: dict = {}
    if wants_rot:
        kw["gif_rot"] = p.get("gif_rot_axis") or "y"
    if wants_bounce:
        deg = _pfloat(p.get("bounce_deg", "")) or 50.0
        axis = p.get("bounce_axis") or None
        kw["gif_bounce"] = (deg, axis) if axis else deg
    if wants_trj:
        kw["gif_trj"] = True
    if wants_ts:
        kw["gif_ts"] = True
    if wants_diffuse:
        kw["gif_diffuse"] = True

    kw["gif_fps"] = _pint(p.get("gif_fps", "")) or 10
    kw["rot_frames"] = _pint(p.get("rot_frames", "")) or 120
    kw["trj_bonds"] = bool(p.get("trj_bonds"))
    kw["detect_nci"] = bool(p.get("detect_nci"))

    if wants_ts:
        vf = _pint(p.get("vib_frames", ""))
        if vf:
            kw["vib_frames"] = vf
    if wants_diffuse:
        kw["diffuse_frames"] = _pint(p.get("diffuse_frames", "")) or 60
        kw["diffuse_noise"] = _pfloat(p.get("diffuse_noise", "")) or 0.3
        kw["diffuse_bonds"] = p.get("diffuse_bonds") or "fade"
        kw["diffuse_reverse"] = bool(p.get("diffuse_reverse"))
        dr = _pint(p.get("diffuse_rot", ""))
        if dr:
            kw["diffuse_rot"] = dr
        if p.get("anchor"):
            kw["anchor"] = p.get("anchor")
    return kw


def _pidx(value: str):
    v = (value or "").strip()
    if v in ("sn", "s", "n"):
        return v
    return False


def _parse_pair_list(value: str) -> Optional[list]:
    """Parse ``"1-2,3-4"`` into 1-indexed integer pairs (render() convention)."""
    value = (value or "").strip()
    if not value:
        return None
    pairs = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        tokens = part.split("-")
        if len(tokens) != 2:
            return None
        try:
            pairs.append((int(tokens[0]), int(tokens[1])))
        except ValueError:
            return None
    return pairs or None


def _parse_pair_list_0(value: str) -> Optional[list]:
    """Parse ``"1-2,3-4"`` into 0-indexed integer pairs (internal convention)."""
    pairs = _parse_pair_list(value)
    if not pairs:
        return None
    return [(a - 1, b - 1) for a, b in pairs]


def _norm_sel(value: str) -> Optional[str]:
    """Normalise a selector spec to comma-separated tokens (``"1-3 M"`` → ``"1-3,M"``)."""
    value = (value or "").strip()
    if not value:
        return None
    tokens = value.replace(",", " ").split()
    return ",".join(tokens) or None


def _parse_label_specs(value: str):
    """Split a ``"1 Et; 2 OH"`` label field into ``["1 Et", "2 OH"]``.

    Each element is tokenised by ``render()`` (whitespace/comma separated), so
    one element is one annotation spec.
    """
    value = (value or "").strip()
    if not value:
        return None
    specs = [chunk.strip() for chunk in value.split(";") if chunk.strip()]
    return specs or None


def _parse_specs(value: str) -> Optional[list]:
    """Split a whitespace/comma separated spec string into tokens.

    Used for ``--unbond`` / ``--bond`` style selectors such as
    ``"M-L sbm Fe-het 1-3"``.
    """
    value = (value or "").strip()
    if not value:
        return None
    tokens = [t for t in value.replace(",", " ").split() if t]
    return tokens or None


def _parse_highlight(value: str) -> Optional[list]:
    """Parse a highlight field into ``[(atoms_spec, color_or_None), ...]``.

    Groups are separated by ``;`` and each group is ``ATOMS [COLOR]``, e.g.
    ``"1-5,8 red; 9-12 blue"``.  A bare single spec (no ``;``) is returned as
    a one-element string list so ``render()`` can auto-colour it.
    """
    value = (value or "").strip()
    if not value:
        return None
    groups: list = []
    for chunk in value.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        parts = chunk.split()
        atoms = parts[0]
        color = parts[1] if len(parts) > 1 else None
        groups.append((atoms, color))
    return groups or None


def _parse_regions(value: str) -> Optional[list]:
    """Parse style regions ``"ATOMS:PRESET; ATOMS:PRESET"``.

    Example: ``"1-6:flat; Fe:tube"``.
    """
    value = (value or "").strip()
    if not value:
        return None
    out: list = []
    for chunk in value.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        if ":" not in chunk:
            return None
        atoms, preset = chunk.rsplit(":", 1)
        out.append((_norm_sel(atoms), preset.strip()))
    return out or None


def _parse_atom_opacity(value: str) -> Optional[list]:
    """Parse atom opacity ``"ATOMS:VALUE; ATOMS:VALUE"`` into selector tuples.

    Example: ``"1-5:0.3; M:0.5"``.  Accepts the legacy single-spec form
    ``"1-5:0.3"``.
    """
    value = (value or "").strip()
    if not value:
        return None
    out: list = []
    for chunk in value.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        if ":" not in chunk:
            return None
        atoms, val = chunk.rsplit(":", 1)
        try:
            out.append((_norm_sel(atoms), float(val.strip())))
        except ValueError:
            return None
    return out or None


def _parse_indices_1based(value: str):
    """Parse ``"1-5,8"`` into a 1-indexed int list, or ``True`` for all atoms.

    Returns ``None`` for an empty field.  This is the convention expected by
    ``render(vdw=...)``.
    """
    value = (value or "").strip()
    if not value:
        return None
    if value.lower() in ("all", "*"):
        return True
    out: list[int] = []
    for part in value.replace(" ", "").split(","):
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            try:
                out.extend(range(int(a), int(b) + 1))
            except ValueError:
                return None
        else:
            try:
                out.append(int(part))
            except ValueError:
                return None
    return out or None


def _parse_radius_scale(value: str) -> Optional[list]:
    """Parse ``"ATOMS:FACTOR; ATOMS:FACTOR"`` into ``(sel, factor)`` tuples.

    Example: ``"1-5,8:2.0; M:1.5"`` — repeatable, ``;``-separated.
    """
    value = (value or "").strip()
    if not value:
        return None
    out: list = []
    for chunk in value.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        if ":" not in chunk:
            return None
        spec, fac = chunk.rsplit(":", 1)
        try:
            out.append((_norm_sel(spec), float(fac.strip())))
        except ValueError:
            return None
    return out or None


def _parse_hull(value: str):
    """Parse the Hull field into the type expected by ``render(hull=...)``.

    Accepts ``"rings"`` / ``"faces"`` / ``"pores"``, or 1-indexed atom ranges
    such as ``"1-6"``, ``"1-6;7-12"`` or ``"1-6 7-12"`` (→ ``[[1..6], [7..12]]``).
    """
    value = (value or "").strip()
    if not value:
        return None
    low = value.lower()
    if low in ("rings", "ring"):
        return "rings"
    if low in ("faces", "face"):
        return "faces"
    if low in ("pores", "pore"):
        return "pores"
    from xyzrender.utils import parse_atom_indices

    groups = [g for g in value.replace(";", " ").split() if g]
    if not groups:
        return None
    out: list = []
    for g in groups:
        try:
            idx = parse_atom_indices(g, one_indexed=True)
        except (ValueError, TypeError):
            return None
        if not idx:
            return None
        out.append(idx)
    return out or None


def _parse_stereo(value: str):
    """Map the Stereo class combo to ``render(stereo=...)``.

    ``"off"``/empty → ``False``; ``"all"`` → ``True`` (every class);
    otherwise a single-class list (e.g. ``["point"]``).
    """
    v = (value or "off").strip().lower()
    if v in ("", "off", "none"):
        return False
    if v == "all":
        return True
    return [v]


def _parse_tuple2(value: str) -> Optional[tuple]:
    value = (value or "").strip()
    if not value:
        return None
    parts = [p.strip() for p in value.split(",")]
    if len(parts) != 2:
        return None
    try:
        return (float(parts[0]), float(parts[1]))
    except ValueError:
        return None


def _svg_to_png(svg_path: str) -> Optional[str]:
    """Convert an SVG preview to PNG via resvg-py.  Returns PNG path."""
    png_path = svg_path + ".preview.png"
    try:
        import resvg_py  # type: ignore
        png_bytes = resvg_py.svg_to_bytes(svg_path=svg_path)
        if isinstance(png_bytes, (bytes, bytearray)):
            Path(png_path).write_bytes(bytes(png_bytes))
            return png_path
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Background render thread (preview only — nothing is written to disk)
# ---------------------------------------------------------------------------

class RenderThread(threading.Thread):
    def __init__(self, params: dict, callback=None, result_queue: Optional["queue.Queue"] = None):
        """Render *params* in the background.

        When *result_queue* is given (the GUI always passes one) this thread
        pushes itself onto the queue and the main thread polls it — Tk widgets
        must never be touched from a worker thread.  Without a queue (plain
        scripts/tests) *callback* is invoked directly.
        """
        super().__init__(daemon=True)
        self.params = params
        self.callback = callback
        self.result_queue = result_queue
        self.error: Optional[Exception] = None
        self.result_svg: Optional[str] = None   # SVG string (static modes)
        self.result_path: Optional[str] = None   # saved path (gif modes)
        self.result_text: Optional[str] = None   # geometry measurement output
        self.preview_gif = False

    def run(self) -> None:
        try:
            self._render()
        except Exception as exc:  # noqa: BLE001
            self.error = exc
        if self.result_queue is not None:
            self.result_queue.put(self)
        elif self.callback is not None:
            self.callback(self)

    def _load_molecule(self, p: dict, input_path, smiles_string):
        """Explicitly load the input molecule (SMILES, ensemble, or file)."""
        charge = p.get("charge", 0)
        multiplicity = p.get("multiplicity")
        kekule = p.get("kekule", False)
        rebuild = p.get("rebuild", False)
        quick = p.get("quick", False)
        nci_detect = p.get("nci_detect", False)

        if smiles_string:
            return api.load(smiles_string, smiles=True, charge=charge,
                            multiplicity=multiplicity, kekule=kekule)

        if p.get("ensemble"):
            return api.load(
                input_path,
                ensemble=True,
                charge=charge,
                multiplicity=multiplicity,
                kekule=kekule,
                rebuild=rebuild,
                quick=quick,
                nci_detect=nci_detect,
                align_atoms=_norm_sel(p.get("align_atoms", "")),
                ensemble_color=p.get("ensemble_color") or None,
                ensemble_opacity=_pfloat(p.get("opacity", "")),
                auto_align=(_pbool(p.get("auto_align", "")) is not False),
            )

        return api.load(
            input_path,
            charge=charge,
            multiplicity=multiplicity,
            kekule=kekule,
            rebuild=rebuild,
            mol_frame=p.get("mol_frame", 0) or 0,
            ts_detect=p.get("ts_detect", False),
            ts_frame=p.get("ts_frame", 0) or 0,
            nci_detect=nci_detect,
            cell=p.get("cell", False),
            quick=quick,
            bohr=(True if p.get("bohr") else None),
        )

    def _render(self) -> None:
        p = self.params
        input_path = p.get("input_path")
        smiles_string = p.get("smiles_string") or None
        output = p.get("output") or None
        wants_gif = _gif_active(p)

        # GIF preview must NOT be written next to the source molecule
        # (render_gif defaults to mol_path.with_suffix(".gif") when
        # output is None) — write it to a temp file instead.
        if wants_gif and output is None:
            import tempfile

            output = str(Path(tempfile.gettempdir()) / "xyzrender_gui_preview.gif")
            self.preview_gif = True

        # ---- Style config (mirrors the CLI's build_config call) ----
        from xyzrender.colors import resolve_color
        from xyzrender.config import build_config

        # Resolve hydrogen display: "Show all H" → True, "Show H atoms" field
        # → 1-indexed list, otherwise None (preset default).
        _hy = True if p.get("hy") else None
        _hy_atoms = _parse_indices_1based(p.get("hy_atoms", ""))
        if isinstance(_hy_atoms, list):
            _hy = _hy_atoms
        elif _hy_atoms is True:
            _hy = True

        preset = p.get("config", "default") or "default"
        cfg = build_config(
            preset,
            canvas_size=_pint(p.get("canvas_size", "")),
            atom_scale=_pfloat(p.get("atom_scale", "")),
            bond_width=_pfloat(p.get("bond_width", "")),
            atom_stroke_width=_pfloat(p.get("atom_stroke_width", "")),
            bond_color=p.get("bond_color") or None,
            bond_outline_color=p.get("bond_outline_color") or None,
            bond_outline_width=_pfloat(p.get("bond_outline_width", "")),
            mo_outline_color=p.get("mo_outline_color") or None,
            mo_outline_width=_pfloat(p.get("mo_outline_width", "")),
            ts_color=p.get("ts_color") or None,
            ts_element=(True if p.get("ts_element") else None),
            ts_dash=_parse_tuple2(p.get("ts_dash", "")),
            ts_width=_pfloat(p.get("ts_width", "")),
            nci_color=p.get("nci_color") or None,
            nci_element=(True if p.get("nci_element") else None),
            nci_dash=_parse_tuple2(p.get("nci_dash", "")),
            nci_width=_pfloat(p.get("nci_width", "")),
            background=p.get("background") or None,
            transparent=p.get("transparent", False),
            gradient=(True if p.get("gradient") else None),
            hue_shift_factor=_pfloat(p.get("hue_shift_factor", "")),
            light_shift_factor=_pfloat(p.get("light_shift_factor", "")),
            saturation_shift_factor=_pfloat(p.get("saturation_shift_factor", "")),
            fog=(True if p.get("fog") else None),
            fog_strength=_pfloat(p.get("fog_strength", "")),
            bo=(True if p.get("bo") else None),
            label_font_size=_pfloat(p.get("label_font_size", "")),
            vdw_opacity=_pfloat(p.get("vdw_opacity", "")),
            vdw_scale=_pfloat(p.get("vdw_scale", "")),
            atom_gradient_strength=_pfloat(p.get("atom_gradient_strength", "")),
            bond_gradient_strength=_pfloat(p.get("bond_gradient_strength", "")),
            vdw_gradient_strength=_pfloat(p.get("vdw_gradient_strength", "")),
            hide_bonds=p.get("hide_bonds", False),
            unbond=_parse_specs(p.get("unbond", "")),
            bond=_parse_specs(p.get("bond", "")),
            hy=_hy,
            no_hy=p.get("no_hy", False),
            orient=_pbool(p.get("orient", "")),
        )

        # ---- Config-only knobs (render()/render_gif() have no matching kwarg) ----
        if p.get("haptic"):
            cfg.haptic = True
        if p.get("skeletal_label_color"):
            cfg.skeletal_label_color = resolve_color(p.get("skeletal_label_color"))
        if p.get("vdw_interlocking"):
            cfg.vdw_interlocking = True
        if p.get("atom_interlocking"):
            cfg.atom_interlocking = True
        _vow = _pfloat(p.get("vdw_outline_width", ""))
        if _vow is not None:
            cfg.vdw_outline_width = _vow
        if p.get("vdw_outline_color"):
            cfg.vdw_outline_color = resolve_color(p.get("vdw_outline_color"))
        _hsc = _pfloat(p.get("h_scale", ""))
        if _hsc is not None:
            cfg.h_scale = _hsc
        _vhsc = _pfloat(p.get("vdw_h_scale", ""))
        if _vhsc is not None:
            cfg.vdw_h_scale = _vhsc

        # ---- Overlay molecule / overlay-specific config ----
        import copy

        overlay_spec = p.get("overlay") or None
        if overlay_spec and p.get("overlay_ts"):
            # Pre-load so TS detection happens on the overlay itself.
            overlay_spec = api.load(overlay_spec, ts_detect=True)

        if p.get("overlay_ts_bond"):
            cfg.overlay = copy.copy(cfg.overlay)
            cfg.overlay.ts_bonds = _parse_pair_list_0(p.get("overlay_ts_bond", "")) or []

        _ov_unbond = _parse_specs(p.get("overlay_unbond", ""))
        _ov_bond = _parse_specs(p.get("overlay_bond", ""))
        _ov_show = _parse_specs(p.get("overlay_show", ""))
        _ov_atom_scale = _pfloat(p.get("overlay_atom_scale", ""))
        _ov_bond_width = _pfloat(p.get("overlay_bond_width", ""))
        overlay_config = None
        if (_ov_unbond or _ov_bond or _ov_show
                or _ov_atom_scale is not None or _ov_bond_width is not None):
            overlay_config = copy.copy(cfg.overlay)
            if _ov_unbond:
                overlay_config.unbond = _ov_unbond
            if _ov_bond:
                overlay_config.bond = _ov_bond
            if _ov_show:
                overlay_config.show = _ov_show
            if _ov_atom_scale is not None:
                overlay_config.atom_scale = _ov_atom_scale
            if _ov_bond_width is not None:
                overlay_config.bond_width = _ov_bond_width

        # ---- Non-style arguments (applied on top of *cfg* by render()) ----
        # Hull params only apply when a hull is active; the "Hull edges"
        # checkbox is a plain bool, so passing hull_edge=False with no hull
        # would otherwise spam "hull params ignored (hull not active)".
        _hull = _parse_hull(p.get("hull"))
        if _hull:
            _hull_color = p.get("hull_color") or None
            _hull_opacity = _pfloat(p.get("hull_opacity", ""))
            _hull_edge = _pbool(p.get("hull_edge", ""))
            _hull_edge_width_ratio = _pfloat(p.get("hull_edge_width_ratio", ""))
            _hull_color_type = p.get("hull_color_type") or None
        else:
            _hull_color = _hull_opacity = _hull_edge = None
            _hull_edge_width_ratio = _hull_color_type = None

        common = dict(
            config=cfg,
            output=output,
            only=_norm_sel(p.get("only", "")),
            exclude=_norm_sel(p.get("exclude", "")),
            mol_color=p.get("mol_color") or None,
            highlight=_parse_highlight(p.get("highlight", "")),
            dof=p.get("dof", False),
            dof_strength=_pfloat(p.get("dof_strength", "")),
            glow=_norm_sel(p.get("glow", "")),
            glow_strength=_pfloat(p.get("glow_strength", "")),
            bond_color_by_element=(True if p.get("bond_color_by_element") else None),
            bond_gradient=(True if p.get("bond_gradient") else None),
            overlay=overlay_spec,
            overlay_color=p.get("overlay_color") or None,
            overlay_config=overlay_config,
            opacity=_pfloat(p.get("opacity", "")),
            align_atoms=_norm_sel(p.get("align_atoms", "")),
            auto_align=_pbool(p.get("auto_align", "")),
            no_cell=p.get("no_cell", False),
            axes=_pbool(p.get("axes", "")),
            axis=p.get("axis") or None,
            supercell=(
                _pint(p.get("supercell_m", "1")) or 1,
                _pint(p.get("supercell_n", "1")) or 1,
                _pint(p.get("supercell_l", "1")) or 1,
            ),
            ghosts=_pbool(p.get("ghosts", "")),
            cell_color=p.get("cell_color") or None,
            cell_width=_pfloat(p.get("cell_width", "")),
            ghost_opacity=_pfloat(p.get("ghost_opacity", "")),
            ref=p.get("ref") or None,
            idx=_pidx(p.get("idx", "")),
            labels=_parse_label_specs(p.get("labels", "")),
            label_file=p.get("label_file") or None,
            stereo=_parse_stereo(p.get("stereo")),
            stereo_style=p.get("stereo_style", "atom") or "atom",
            vector=p.get("vector") or None,
            vector_scale=_pfloat(p.get("vector_scale", "")),
            vector_color=p.get("vector_color") or None,
            surface_style=p.get("surface_style", "solid") or "solid",
            hull=_hull,
            hull_color=_hull_color,
            hull_opacity=_hull_opacity,
            hull_edge=_hull_edge,
            hull_edge_width_ratio=_hull_edge_width_ratio,
            hull_color_type=_hull_color_type,
            pore=p.get("pore", False),
            pore_color=p.get("pore_color") or None,
            pore_opacity=_pfloat(p.get("pore_opacity", "")),
            ring_max_size=_pint(p.get("ring_max_size", "100")) or 100,
            ring_min_size=_pint(p.get("ring_min_size", "3")) or 3,
            face_planarity=_pfloat(p.get("face_planarity", "0.25")) or 0.25,
            mo=p.get("mo", False),
            dens=p.get("dens", False),
            esp=p.get("esp") or None,
            nci=p.get("nci") or None,
            iso=_pfloat(p.get("iso", "")),
            mo_pos_color=p.get("mo_pos_color") or None,
            mo_neg_color=p.get("mo_neg_color") or None,
            mo_blur=_pfloat(p.get("mo_blur", "")),
            mo_upsample=_pint(p.get("mo_upsample", "")),
            flat_mo=p.get("flat_mo", False),
            dens_color=p.get("dens_color") or None,
            nci_mode=(p.get("nci_mode") or None) if p.get("nci") else None,
            nci_cutoff=_pfloat(p.get("nci_cutoff", "")),
            ts_bonds=_parse_pair_list(p.get("ts_bonds", "")),
            nci_bonds=_parse_pair_list(p.get("nci_bonds", "")),
            vdw=_parse_indices_1based(p.get("vdw_indices", "")),
            radius_scale=_parse_radius_scale(p.get("radius_scale", "")),
            cmap=p.get("cmap") or None,
            cmap_range=_parse_tuple2(p.get("cmap_range", "")),
            cmap_palette=p.get("cmap_palette") or None,
            cmap_symm=p.get("cmap_symm", False),
            cbar=p.get("cbar", False),
            regions=_parse_regions(p.get("regions", "")),
            atom_opacity=_parse_atom_opacity(p.get("atom_opacity", "")),
        )

        # ---- Explicit load only when a feature needs the graph object ----
        measure_modes = [m for m, k in
                         (("d", "measure_d"), ("a", "measure_a"), ("t", "measure_t"))
                         if p.get(k)]
        need_mol = bool(p.get("ensemble") or measure_modes or p.get("interactive")
                        or smiles_string)
        mol = None
        if need_mol:
            mol = self._load_molecule(p, input_path, smiles_string)
            if measure_modes:
                import contextlib
                import io

                from xyzrender.measure import print_measurements
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    print_measurements(mol.graph, measure_modes)
                self.result_text = buf.getvalue()
            if p.get("interactive"):
                try:
                    api.orient(mol, viewer=p.get("viewer") or "vmol")
                except Exception as exc:  # noqa: BLE001
                    self.result_text = (self.result_text or "") + \
                        f"\n[interactive viewer] {exc}"

        # Parameters that static render() accepts but render_gif() does NOT.
        _GIF_STATIC_ONLY = {
            "idx", "labels", "label_file", "stereo", "stereo_style",
            "cmap", "cmap_range", "cmap_palette", "cmap_symm", "cbar",
            # Surface cube inputs only for static render(); render_gif() uses
            # mo/dens + cube_data from the loaded molecule instead.
            "esp", "nci", "nci_mode", "nci_cutoff",
            # Manual bond overlays and per-atom opacity — static render only.
            "ts_bonds", "nci_bonds", "vdw", "atom_opacity",
        }

        if wants_gif:
            gif_common = {k: v for k, v in common.items() if k not in _GIF_STATIC_ONLY}
            gif_common.update(_gif_kwargs(p))
            if p.get("gif_trj") or p.get("gif_ts"):
                if smiles_string:
                    msg = ("GIF trajectory / TS-vibration modes require a file "
                           "input, not SMILES")
                    raise ValueError(msg)
                # The trajectory is read from disk; forward the loaded graph so
                # -I orientation / TS/NCI bonds are respected.
                gif_common["reference_graph"] = mol.graph if mol is not None else None
                api.render_gif(input_path, **gif_common)
            else:
                target = mol if mol is not None else input_path
                api.render_gif(target, **gif_common)
            self.result_path = output
        else:
            if mol is not None:
                res = api.render(mol, **common)
            else:
                res = api.render(input_path, **common)
            self.result_svg = str(res)
            self.result_path = output


# ---------------------------------------------------------------------------
# Scrollable frame helper
# ---------------------------------------------------------------------------

class ScrollFrame(ttk.Frame):
    """A ttk.Frame with a vertical scrollbar; add children to .inner."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        # White card look: white canvas with a subtle border ring.
        self.canvas = tk.Canvas(self, highlightthickness=1,
                                highlightbackground=BORDER, bg=CARD)
        self.scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self._window_id = self.canvas.create_window((0, 0), window=self.inner, anchor=tk.NW)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._on_wheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self._window_id, width=event.width)

    def _on_wheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


# ---------------------------------------------------------------------------
# Field builders (pack-based, robust against label length changes)
# ---------------------------------------------------------------------------

def _hbox(parent, pady=2, padx=4):
    """A horizontal frame inside parent; children pack left-to-right."""
    f = ttk.Frame(parent)
    f.pack(fill=tk.X, pady=pady, padx=padx)
    return f


def _field(parent, label, variable, width=ENTRY_W, tip=None, pady=2, padx=4, color=False):
    """label + Entry in one row. Entry expands to fill remaining width."""
    f = _hbox(parent, pady=pady, padx=padx)
    ttk.Label(f, text=_(label), width=18, anchor=tk.E).pack(side=tk.LEFT, padx=(0, 6))
    ent = ttk.Entry(f, textvariable=variable, width=width)
    ent.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
    if color:
        btn = ttk.Button(f, text=_("Choose…"), width=8,
                         command=lambda e=ent: _pick_color(e))
        btn.pack(side=tk.LEFT, padx=(4, 0))
        _tip_widget(btn, _("Pick a colour"))
    if tip:
        _tip_widget(ent, _(tip))
    return ent


def _pick_color(entry):
    """Open a colour chooser and write the hex value into *entry*."""
    from tkinter import colorchooser
    result = colorchooser.askcolor(title=_("Choose colour"), parent=entry)
    if result and result[1]:
        entry.delete(0, tk.END)
        entry.insert(0, result[1])


def _check(parent, text, variable, tip=None, pady=1, padx=4):
    f = _hbox(parent, pady=pady, padx=padx)
    cb = ttk.Checkbutton(f, text=_(text), variable=variable)
    cb.pack(side=tk.LEFT)
    if tip:
        _tip_widget(cb, _(tip))
    return cb


def _combo(parent, label, variable, values, width=14, tip=None, pady=2, padx=4):
    f = _hbox(parent, pady=pady, padx=padx)
    ttk.Label(f, text=_(label), width=18, anchor=tk.E).pack(side=tk.LEFT, padx=(0, 6))
    cb = ttk.Combobox(f, textvariable=variable, values=values, width=width, state="readonly")
    cb.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
    if tip:
        _tip_widget(cb, _(tip))
    return cb


def _button_row(parent, items, pady=2, padx=4):
    """items: list of (text, command_or_None, width)."""
    f = _hbox(parent, pady=pady, padx=padx)
    for text, cmd, width in items:
        b = ttk.Button(f, text=_(text), command=cmd, width=width)
        b.pack(side=tk.LEFT, padx=(0, 6))
    return f


def _sep(parent, text=None, pady=6, padx=4):
    if text:
        f = _hbox(parent, pady=pady, padx=padx)
        ttk.Label(f, text=_(" " + text + " "), font=("Segoe UI", 9, "bold"),
                  foreground="#555555").pack(side=tk.LEFT)
        ttk.Separator(f, orient=tk.HORIZONTAL).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0))
    else:
        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=pady, padx=padx)


# Tooltip shared by all builders.
def _tip_widget(widget, text):
    def _enter(_e):
        win = tk.Toplevel(widget)
        win.wm_overrideredirect(True)
        win.wm_geometry(f"+{widget.winfo_rootx()+20}+{widget.winfo_rooty()+10}")
        lbl = tk.Label(win, text=text, background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                       font=("Segoe UI", 8, "bold"), padx=4, pady=2, justify=tk.LEFT)
        lbl.pack()
        widget._tip_win = win
    def _leave(_e):
        win = getattr(widget, "_tip_win", None)
        if win is not None:
            try:
                win.destroy()
            except tk.TclError:
                pass
            widget._tip_win = None
    widget.bind("<Enter>", _enter)
    widget.bind("<Leave>", _leave)


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------

class XyzrenderGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        # Default language: Chinese (must be set before any UI is built)
        set_lang("zh")
        self.title(_(APP_TITLE_EN))
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = min(1500, sw - 40), min(1010, sh - 70)
        self.geometry(f"{w}x{h}+{max(0, (sw - w) // 2)}+{max(0, (sh - h) // 2 - 20)}")
        self.minsize(1100, 720)

        self.status_var = tk.StringVar(value=_("Ready"))

        # Worker threads post themselves here; the main thread polls and runs
        # the UI callbacks (Tk widgets may only be touched from the main thread).
        self._result_queue: "queue.Queue" = queue.Queue()

        self._build_menu()
        self._create_widgets()
        self._bind_events()

        self._last_output: Optional[str] = None
        self._preview_image: Optional[ImageTk.PhotoImage] = None
        self._preview_path: Optional[str] = None
        self._rendered_svg: Optional[str] = None   # last rendered SVG string
        self._thread: Optional[RenderThread] = None

        self.after(50, self._poll_results)

    # -- background result polling ----------------------------------------
    def _poll_results(self):
        """Drain finished render threads and run their UI callbacks."""
        try:
            while True:
                thread = self._result_queue.get_nowait()
                cb = getattr(thread, "callback", None)
                if cb is not None:
                    try:
                        cb(thread)
                    except tk.TclError:
                        return  # window is closing
        except queue.Empty:
            pass
        try:
            self.after(50, self._poll_results)
        except tk.TclError:
            pass

    # -- menu -------------------------------------------------------------
    def _build_menu(self):
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label=_("Open input file…"), command=self._browse_input)
        file_menu.add_command(label=_("Save output…"), command=self._on_save)
        file_menu.add_command(label=_("Open output file…"), command=self._on_open_output)
        file_menu.add_separator()
        file_menu.add_command(label=_("Exit"), command=self.destroy)
        menubar.add_cascade(label=_("File"), menu=file_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label=_("About"), command=self._about)
        help_menu.add_separator()
        # Language submenu
        lang_menu = tk.Menu(help_menu, tearoff=0)
        for code, name in LANGUAGES.items():
            lang_menu.add_radiobutton(
                label=name, value=code,
                command=lambda c=code: self._set_lang_from_menu(c),
            )
        help_menu.add_cascade(label=_("Language"), menu=lang_menu)
        menubar.add_cascade(label=_("Help"), menu=help_menu)

        for m in (menubar, file_menu, help_menu, lang_menu):
            m.configure(bg=CARD, fg=TEXT,
                        activebackground=SELECT_BG, activeforeground=TEXT,
                        disabledforeground=MUTED, font=("Segoe UI", 9, "bold"),
                        borderwidth=0, relief="flat")

        self.config(menu=menubar)

    def _about(self):
        win = tk.Toplevel(self)
        win.title(_("About xyzrender GUI"))
        win.configure(bg=CARD)
        win.transient(self)
        win.resizable(False, False)

        pad = ttk.Frame(win, style="Toolbar.TFrame", padding=18)
        pad.pack(fill=tk.BOTH, expand=True)

        ttk.Label(pad, text="xyzrender", style="Brand.TLabel").pack(anchor=tk.W)
        ttk.Label(pad, text=APP_TITLE_EN, style="Version.TLabel").pack(anchor=tk.W, pady=(2, 0))
        ttk.Label(pad, text=_("Publication-quality molecular graphics GUI."),
                  style="Toolbar.TLabel").pack(anchor=tk.W, pady=(2, 10))
        ttk.Separator(pad).pack(fill=tk.X, pady=(0, 10))

        def row(label, value, wrap=0):
            f = ttk.Frame(pad, style="Toolbar.TFrame")
            f.pack(fill=tk.X, pady=1)
            ttk.Label(f, text=_(label), style="Toolbar.TLabel", foreground=MUTED,
                      width=13, anchor=tk.NW).pack(side=tk.LEFT, anchor=tk.NW)
            ttk.Label(f, text=value, style="Toolbar.TLabel", justify=tk.LEFT,
                      wraplength=wrap).pack(side=tk.LEFT, anchor=tk.W)
            return f

        row("Author:", AUTHOR_NAME)
        row("Postal Code:", AUTHOR_POSTAL)

        email_row = row("Email:", AUTHOR_EMAIL)
        ttk.Button(email_row, text=_("Copy"),
                   command=lambda: self._copy_text(AUTHOR_EMAIL)).pack(side=tk.LEFT, padx=(10, 0))

        ttk.Separator(pad).pack(fill=tk.X, pady=(10, 10))
        ttk.Label(pad,
                  text=_("Built on the open-source xyzrender library by Alister S. Goodfellow. If you use this software, please cite it."),
                  style="Toolbar.TLabel", wraplength=430, justify=tk.LEFT).pack(anchor=tk.W)

        proj_row = row("Project:", PROJECT_URL)
        ttk.Button(proj_row, text=_("Copy"), command=lambda: self._copy_text(PROJECT_URL)).pack(side=tk.LEFT, padx=(10, 0))
        ttk.Button(proj_row, text=_("Open"), command=lambda: webbrowser.open(PROJECT_URL)).pack(side=tk.LEFT, padx=(6, 0))

        btns = ttk.Frame(pad, style="Toolbar.TFrame")
        btns.pack(fill=tk.X, pady=(16, 0))
        ttk.Button(btns, text=_("Close"), style="Accent.TButton",
                   command=win.destroy).pack(side=tk.RIGHT)

        win.bind("<Escape>", lambda _e: win.destroy())
        win.update_idletasks()
        x = self.winfo_rootx() + max(0, (self.winfo_width() - win.winfo_width()) // 2)
        y = self.winfo_rooty() + max(0, (self.winfo_height() - win.winfo_height()) // 3)
        win.geometry(f"+{x}+{y}")
        win.grab_set()

    def _copy_text(self, text: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(text)
        self.status_var.set(_("Copied: ") + text)

    # -- widgets ----------------------------------------------------------
    def _create_widgets(self):
        # ----- Global styling: modern flat look -----
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        self.configure(bg=BG)

        # Base: most surfaces are white cards on a light grey window
        style.configure(".", font=("Segoe UI", 9, "bold"), background=CARD, foreground=TEXT)
        style.configure("TFrame", background=CARD)
        style.configure("TLabel", background=CARD, foreground=TEXT)
        style.configure("Bg.TFrame", background=BG)
        style.configure("Bg.TLabel", background=BG, foreground=TEXT)
        style.configure("Muted.TLabel", background=CARD, foreground=MUTED)

        # Buttons: flat white with hairline border; accent variant for primary
        style.configure("TButton", background=CARD, foreground=TEXT,
                        bordercolor=BORDER, focusthickness=1, focuscolor=CARD,
                        padding=(10, 5), font=("Segoe UI", 9, "bold"))
        style.map("TButton",
                  background=[("active", "#e9eef7"), ("pressed", "#dfe7f5")],
                  bordercolor=[("active", ACCENT)],
                  foreground=[("disabled", "#a4acb9")])
        style.configure("Accent.TButton", background=ACCENT, foreground="#ffffff",
                        bordercolor=ACCENT, focusthickness=1, focuscolor=ACCENT,
                        padding=(16, 6), font=("Segoe UI", 9, "bold"))
        style.map("Accent.TButton",
                  background=[("active", ACCENT_DK), ("pressed", ACCENT_DK)],
                  foreground=[("disabled", "#c8d3ea")])

        # Inputs
        style.configure("TEntry", fieldbackground=CARD, bordercolor=BORDER,
                        lightcolor=BORDER, padding=4, insertcolor=TEXT)
        style.map("TEntry", bordercolor=[("focus", ACCENT)], lightcolor=[("focus", ACCENT)])
        style.configure("TCombobox", fieldbackground=CARD, bordercolor=BORDER,
                        arrowcolor=MUTED, padding=4)
        style.map("TCombobox",
                  fieldbackground=[("readonly", CARD)],
                  bordercolor=[("focus", ACCENT)],
                  lightcolor=[("focus", ACCENT)])

        # Check / radio
        style.configure("TCheckbutton", background=CARD, foreground=TEXT,
                        indicatorcolor=CARD, padding=(0, 2))
        style.map("TCheckbutton",
                  indicatorcolor=[("selected", ACCENT), ("active", "#c9d8f7")])
        style.configure("TRadiobutton", background=CARD, foreground=TEXT,
                        indicatorcolor=CARD)
        style.map("TRadiobutton", indicatorcolor=[("selected", ACCENT)])

        # Notebook + tabs: active tab is white (merges with content),
        # inactive tabs recede into the grey window background.
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=TOOL_BG, foreground=MUTED,
                        padding=(14, 7), borderwidth=0, font=("Segoe UI", 9, "bold"))
        style.map("TNotebook.Tab",
                  background=[("selected", CARD)],
                  foreground=[("selected", ACCENT), ("active", TEXT)],
                  padding=[("selected", (14, 8))])

        # LabelFrame: white card group with accent-coloured caption
        style.configure("TLabelframe", background=CARD, foreground=TEXT,
                        bordercolor=BORDER, borderwidth=1, relief="groove",
                        padding=(6, 4))
        style.configure("TLabelframe.Label", background=CARD, foreground=ACCENT,
                        font=("Segoe UI", 9, "bold"))

        # Treeview
        style.configure("Treeview", background=CARD, fieldbackground=CARD,
                        foreground=TEXT, rowheight=26, borderwidth=0,
                        font=("Segoe UI", 9, "bold"))
        style.configure("Treeview.Heading", background=TOOL_BG, foreground=TEXT,
                        relief="flat", font=("Segoe UI", 9, "bold"), padding=5)
        style.map("Treeview.Heading", background=[("active", "#d8deea")])
        style.map("Treeview",
                  background=[("selected", SELECT_BG)],
                  foreground=[("selected", TEXT)])

        # Scrollbar / progress / sash / separator
        style.configure("TScrollbar", background="#c7ced9", troughcolor=CARD,
                        bordercolor=CARD, arrowcolor=MUTED, borderwidth=0)
        style.map("TScrollbar", background=[("active", "#aeb8c6")])
        style.configure("Horizontal.TProgressbar", background=ACCENT,
                        troughcolor=TOOL_BG, bordercolor=BAR_BG, lightcolor=ACCENT,
                        thickness=8)
        style.configure("TPanedwindow", sashwidth=6, sashbackground="#c3cbd8")
        style.configure("TSeparator", background=BORDER)

        # Bars
        style.configure("Toolbar.TFrame", background=CARD)
        style.configure("Toolbar.TLabel", background=CARD, foreground=TEXT)
        style.configure("Brand.TLabel", background=CARD, foreground=ACCENT,
                        font=("Segoe UI", 17, "bold"))
        style.configure("Version.TLabel", background=CARD, foreground=MUTED,
                        font=("Segoe UI", 9, "bold"))
        style.configure("Status.TFrame", background=BAR_BG)
        style.configure("Status.TLabel", background=BAR_BG, foreground=MUTED,
                        font=("Segoe UI", 8, "bold"))
        # Preview page: light frame surrounding the white canvas
        style.configure("Preview.TFrame", background="#f7f8fb",
                        borderwidth=1, relief="solid")

        # ----- Top toolbar: white strip, brand on the left, actions grouped -----
        toolbar = ttk.Frame(self, padding=(12, 7), style="Toolbar.TFrame")
        toolbar.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(toolbar, text="xyzrender", style="Brand.TLabel").pack(side=tk.LEFT)
        ttk.Label(toolbar, text=f"v{xyzrender.__version__}",
                  style="Version.TLabel").pack(side=tk.LEFT, padx=(4, 0), pady=(6, 0))
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=12)

        ttk.Button(toolbar, text=_("Open input file…"), command=self._browse_input).pack(side=tk.LEFT, padx=(0, 6))
        self.btn_render_toolbar = ttk.Button(toolbar, text=_("Render"), style="Accent.TButton",
                                             command=self._on_render)
        self.btn_render_toolbar.pack(side=tk.LEFT, padx=(0, 6))
        self.btn_save_toolbar = ttk.Button(toolbar, text=_("Save"), command=self._on_save, state=tk.DISABLED)
        self.btn_save_toolbar.pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(toolbar, text=_("Open output file…"), command=self._on_open_output).pack(side=tk.LEFT)

        ttk.Separator(self, orient=tk.HORIZONTAL).pack(side=tk.TOP, fill=tk.X)

        # ----- Main paned: left(params) | centre(preview) -----
        self.paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.paned.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))

        # Left: vertical icon toolbar + scrollable params panel
        self.left = ttk.Frame(self.paned, width=530)
        self.paned.add(self.left, weight=1)

        # Scrollable params panel was previously a single tall column; the
        # parameter area is now a two-level notebook so a single page fits.
        inner = self.left  # kept for readability of the code below

        # Molecule tree at the top of the left column (fixed height)
        tree_frame = ttk.LabelFrame(inner, text=_("Molecules"), padding=6)
        tree_frame.pack(side=tk.TOP, fill=tk.X, padx=6, pady=(6, 4))

        cols = ("name", "type")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=4)
        self.tree.heading("name", text=_("Name"))
        self.tree.heading("type", text=_("Type"))
        self.tree.column("name", width=120, stretch=True)
        self.tree.column("type", width=40, stretch=False)
        self.tree.pack(fill=tk.BOTH, expand=True)

        tbtnf = ttk.Frame(tree_frame)
        tbtnf.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(tbtnf, text=_("Add file…"), command=self._browse_input).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        ttk.Button(tbtnf, text=_("Remove"), command=self._remove_selected).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))
        ttk.Label(tree_frame, text=_("Click a structure to load and preview it."),
                  foreground=MUTED, font=("Segoe UI", 8, "bold")).pack(fill=tk.X, pady=(3, 0))

        # ----- Two-level parameter area: group (level 1) → page (level 2) -----
        # Only one page is on screen at a time, so pages fit the panel
        # height instead of stacking four notebooks' worth of content.
        self.nb_top = ttk.Notebook(inner)
        self.nb_top.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))

        _GROUPS = (
            (_("Essentials"), (
                ("tab_basic", "Basic"),
                ("tab_loading", "Loading"),
                ("tab_style", "Styling"),
                ("tab_display", "Display"),
            )),
            (_("Motion / NCI"), (
                ("tab_orient", "Orientation"),
                ("tab_tsnci", "TS / NCI"),
                ("tab_gif", "GIF Animation"),
            )),
            (_("Surfaces / Annotations"), (
                ("tab_surface", "Surfaces"),
                ("tab_overlay", "Overlay / Crystal"),
                ("tab_annot", "Annotations"),
                ("tab_vector", "Vectors"),
            )),
            (_("Crystal / Measure"), (
                ("tab_highlight", "Highlights"),
                ("tab_hullpore", "Hull / Pore"),
                ("tab_crystal", "Crystal"),
                ("tab_measure", "Measure"),
            )),
        )
        for group_label, pages in _GROUPS:
            group = ttk.Frame(self.nb_top)
            self.nb_top.add(group, text=group_label)
            sub = ttk.Notebook(group)
            sub.pack(fill=tk.BOTH, expand=True)
            for attr, label in pages:
                frame = ScrollFrame(sub)
                sub.add(frame, text=_(label))
                setattr(self, attr, frame)

        # Default group / page: Essentials → Basic
        self.nb_top.select(0)
        for child in self.nb_top.winfo_children():
            for sub in child.winfo_children():
                if isinstance(sub, ttk.Notebook):
                    sub.select(0)

        self._fill_basic()
        self._fill_loading()
        self._fill_style()
        self._fill_display()
        self._fill_orient()
        self._fill_tsnci()
        self._fill_gif()
        self._fill_surface()
        self._fill_overlay()
        self._fill_annot()
        self._fill_vector()
        self._fill_highlight()
        self._fill_hullpore()
        self._fill_crystal()
        self._fill_measure()

        # Centre: fixed-size preview canvas (not stretched by window resizing)
        self.centre = ttk.Frame(self.paned, width=880, height=680, style="Preview.TFrame")
        self.centre.pack_propagate(False)
        self.centre.grid_propagate(False)
        self.centre.rowconfigure(0, weight=1)
        self.centre.columnconfigure(0, weight=1)
        self.paned.add(self.centre, weight=0)
        self.centre.rowconfigure(0, weight=1)
        self.centre.columnconfigure(0, weight=1)

        prev_frame = ttk.Frame(self.centre, style="Preview.TFrame")
        prev_frame.grid(row=0, column=0, sticky=tk.NSEW, padx=8, pady=8)
        prev_frame.rowconfigure(0, weight=1)
        prev_frame.columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(prev_frame, bg=CARD, highlightthickness=1,
                                highlightbackground=BORDER)
        self.hsb = ttk.Scrollbar(prev_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.vsb = ttk.Scrollbar(prev_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=self.hsb.set, yscrollcommand=self.vsb.set)
        self.canvas.grid(row=0, column=0, sticky=tk.NSEW)
        self.hsb.grid(row=1, column=0, sticky=tk.EW)
        self.vsb.grid(row=0, column=1, sticky=tk.NS)

        self.canvas.create_text(
            440, 320,
            text=_("No structure loaded.") + "\n" +
                 _("Open a molecule, then click Render to preview here."),
            fill=MUTED, justify=tk.CENTER, font=("Segoe UI", 13, "bold"),
            tags="placeholder",
        )

        # ----- Bottom control bar -----
        ttk.Separator(self, orient=tk.HORIZONTAL).pack(side=tk.BOTTOM, fill=tk.X)
        bottom = ttk.Frame(self, padding=(12, 8), style="Toolbar.TFrame")
        bottom.pack(side=tk.BOTTOM, fill=tk.X)

        self.btn_render = ttk.Button(bottom, text=_("Render"), style="Accent.TButton",
                                     command=self._on_render)
        self.btn_render.pack(side=tk.LEFT, padx=(0, 8))
        self.btn_save = ttk.Button(bottom, text=_("Save"), command=self._on_save, state=tk.DISABLED)
        self.btn_save.pack(side=tk.LEFT, padx=(0, 8))
        self.btn_open = ttk.Button(bottom, text=_("Open output"), command=self._on_open_output, state=tk.DISABLED)
        self.btn_open.pack(side=tk.LEFT, padx=(0, 8))

        self.progress = ttk.Progressbar(bottom, mode="indeterminate", length=180)
        self.progress.pack(side=tk.RIGHT, padx=(8, 0))

        self.var_rendering = tk.StringVar(value=_("Idle"))
        ttk.Label(bottom, textvariable=self.var_rendering,
                  style="Toolbar.TLabel", foreground=MUTED).pack(side=tk.RIGHT, padx=(0, 12))

        # ----- Status bar (packed last so it sits at the very bottom) -----
        status_bar = ttk.Label(self, textvariable=self.status_var, style="Status.TLabel",
                               anchor=tk.W, padding=(12, 3))
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    # -- language ---------------------------------------------------------
    def _set_lang_from_menu(self, code: str):
        set_lang(code)
        self._rebuild_ui()

    def _rebuild_ui(self):
        for child in self.winfo_children():
            child.destroy()
        self._build_menu()
        self._create_widgets()

    # -- tree -------------------------------------------------------------
    def _add_molecule_to_tree(self, path: str):
        name = Path(path).name
        ftype = Path(path).suffix.lower().lstrip(".") or "file"
        iid = self.tree.insert("", tk.END, values=(name, ftype))
        self.tree.item(iid, tags=(path,))
        return iid

    def _remove_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        for item in sel:
            self.tree.delete(item)

    def _tree_selected_path(self):
        sel = self.tree.selection()
        if not sel:
            return None
        tags = self.tree.item(sel[0], "tags")
        return tags[0] if tags else None

    # -- file dialogs -----------------------------------------------------
    def _browse_input(self):
        path = filedialog.askopenfilename(title=_("Open input file"), filetypes=[INPUT_EXTENSIONS, ALL_FILES])
        if path:
            self._add_molecule_to_tree(path)
            self.var_input.set(path)
            if not self.var_output.get().strip():
                self.var_output.set(str(Path(path).with_suffix("." + self.var_out_fmt.get())))
            # self.log_message(_("Added: ") + path)
            children = self.tree.get_children()
            if children:
                last = children[-1]
                self.tree.selection_set(last)
                self.tree.focus(last)
                self.tree.see(last)
            # Preview the newly loaded structure right away.
            self._on_render()

    def _browse_output(self):
        fmt = self.var_out_fmt.get()
        path = filedialog.asksaveasfilename(
            title=_("Save output as"), defaultextension="." + fmt,
            filetypes=[(fmt.upper() + " files", "*." + fmt), ALL_FILES],
        )
        if path:
            self.var_output.set(path)

    def _on_open_output(self):
        if self._last_output and Path(self._last_output).exists():
            os.startfile(self._last_output)

    def _bind_events(self):
        self.var_out_fmt.trace_add("write", lambda *a: self._auto_output_ext())
        # Selecting a molecule in the list loads (and previews) that structure.
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        # Double-click forces a fresh render of the clicked structure.
        self.tree.bind("<Double-1>", lambda _e: self._on_render())

    def _on_tree_select(self, _event=None):
        """Load + preview the molecule clicked in the Molecules list."""
        path = self._tree_selected_path()
        if not path:
            return
        if not Path(path).exists():
            self.status_var.set(_("File not found: ") + path)
            return
        current = self.var_input.get().strip()
        if path == current:
            return  # same structure already loaded — nothing to do
        self.var_input.set(path)
        out = self.var_output.get().strip()
        if not out or Path(out).stem == Path(current).stem:
            self.var_output.set(str(Path(path).with_suffix("." + self.var_out_fmt.get())))
        self.status_var.set(_("Loaded: ") + Path(path).name)
        self._on_render()

    def _auto_output_ext(self):
        fmt = self.var_out_fmt.get()
        inp = self.var_input.get().strip()
        out = self.var_output.get().strip()
        if inp and out and Path(out).stem == Path(inp).stem:
            self.var_output.set(str(Path(inp).with_suffix("." + fmt)))

    def show_preview_from_svg(self, svg_str: str):
        import tempfile
        tmp = Path(tempfile.gettempdir()) / "xyzrender_gui_preview.svg"
        tmp.write_text(svg_str, encoding="utf-8")
        self.show_preview(str(tmp))

    def show_preview(self, path: Optional[str]):
        if not path or not Path(path).exists():
            return
        self._preview_path = path
        self.canvas.delete("all")
        self._preview_image = None

        disp_path = path
        if path.lower().endswith(".svg") and _PIL_OK:
            conv = _svg_to_png(path)
            if conv:
                disp_path = conv

        if not _PIL_OK:
            self.canvas.create_text(
                420, 320,
                text=_("Rendered: ") + Path(path).name + "\n" + _("(PIL not available for image preview)"),
                fill=MUTED, justify=tk.CENTER,
            )
            return

        try:
            img = Image.open(disp_path)
            img.thumbnail((PREVIEW_MAX, PREVIEW_MAX), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self._preview_image = photo
            self.canvas.config(scrollregion=(0, 0, img.width, img.height))
            # Center the image on the canvas (not top-left).
            self.canvas.update_idletasks()
            cw = max(self.canvas.winfo_width(), img.width)
            ch = max(self.canvas.winfo_height(), img.height)
            self.canvas.create_image(cw // 2, ch // 2, image=photo, anchor=tk.CENTER)
        except Exception as exc:  # noqa: BLE001
            self.canvas.create_text(
                420, 320,
                text=_("Rendered: ") + Path(path).name + "\n" + _("Preview unavailable: ") + str(exc),
                fill=MUTED, justify=tk.CENTER,
            )

    # =====================================================================
    # Tab fillers (pack-based rows)
    # =====================================================================

    def _fill_basic(self):
        inner = self.tab_basic.inner

        self.var_input = tk.StringVar()
        self.var_output = tk.StringVar()
        self.var_out_fmt = tk.StringVar(value="svg")
        self.var_preset = tk.StringVar(value="default")
        self.var_smiles = tk.StringVar()
        self.var_canvas_size = tk.StringVar()
        self.var_atom_scale = tk.StringVar()
        self.var_bond_width = tk.StringVar()
        self.var_background = tk.StringVar()
        self.var_transparent = tk.BooleanVar(value=False)
        self.var_charge = tk.StringVar(value="0")
        self.var_mult = tk.StringVar(value="")

        fr = ttk.LabelFrame(inner, text=_("Input / Output"), padding=6)
        fr.pack(fill=tk.X, pady=(0, 3))
        _field(fr, "Input file:", self.var_input, tip="Molecule file (XYZ, mol, SDF, CIF, …)")
        _button_row(fr, [(_("Browse…"), self._browse_input, BROWSE_W)])
        _field(fr, "Output file:", self.var_output)
        _button_row(fr, [(_("Browse…"), self._browse_output, BROWSE_W)])
        _combo(fr, "Format:", self.var_out_fmt, OUTPUT_FORMATS, width=8)
        _field(fr, "SMILES:", self.var_smiles, tip="Or render from a SMILES string")

        fr2 = ttk.LabelFrame(inner, text=_("Rendering preset"), padding=6)
        fr2.pack(fill=tk.X, pady=(0, 3))
        _combo(fr2, "Preset:", self.var_preset, PRESETS, width=14,
               tip="default, flat, paton, skeletal, bubble, tube, mtube, wire, graph, pmol, vdw, btube")
        _field(fr2, "Canvas (px):", self.var_canvas_size, width=TINY_W,
               tip="Square canvas size in pixels")
        _field(fr2, "Atom scale:", self.var_atom_scale, width=TINY_W, tip="Atom radius multiplier")
        _field(fr2, "Bond width:", self.var_bond_width, width=TINY_W, tip="Bond line width")
        _field(fr2, "Background:", self.var_background, width=10, tip="Hex or named colour", color=True)
        _check(fr2, "Transparent", self.var_transparent, tip="Transparent background")

        fr3 = ttk.LabelFrame(inner, text=_("Charge / Multiplicity"), padding=6)
        fr3.pack(fill=tk.X, pady=(0, 3))
        _field(fr3, "Charge:", self.var_charge, width=TINY_W)
        _field(fr3, "Mult:", self.var_mult, width=TINY_W)

    # ------------------------------------------------------------- loading
    def _fill_loading(self):
        inner = self.tab_loading.inner
        self.var_kekule = tk.BooleanVar(value=False)
        self.var_rebuild = tk.BooleanVar(value=False)
        self.var_bohr = tk.BooleanVar(value=False)
        self.var_mol_frame = tk.StringVar(value="0")
        self.var_quick = tk.BooleanVar(value=False)
        self.var_ensemble = tk.BooleanVar(value=False)
        self.var_ensemble_color = tk.StringVar()

        fr = ttk.LabelFrame(inner, text=_("Molecule loading"), padding=6)
        fr.pack(fill=tk.X, pady=(0, 3))
        _check(fr, "Kekulé structure", self.var_kekule,
               tip="Aromatic perception → Kekulé bond orders")
        _check(fr, "Rebuild topology", self.var_rebuild,
               tip="Re-detect bonds from coordinates")
        _check(fr, "Bohr coordinates", self.var_bohr,
               tip="Interpret input coordinates as Bohr")
        _field(fr, "Frame:", self.var_mol_frame, width=TINY_W,
               tip="Frame index to load from a multi-frame file")
        _check(fr, "Quick", self.var_quick,
               tip="Fast bond perception (skip some refinement)")

        fr2 = ttk.LabelFrame(inner, text=_("Ensemble"), padding=6)
        fr2.pack(fill=tk.X, pady=(0, 3))
        _check(fr2, "Render ensemble", self.var_ensemble,
               tip="Overlay all frames of a multi-frame file")
        _field(fr2, "Ensemble colour:", self.var_ensemble_color, width=10, color=True,
               tip="Comma-separated colours, or a palette name")

    # ---------------------------------------------------------------- style
    def _fill_style(self):
        inner = self.tab_style.inner
        self.var_grad = tk.BooleanVar(value=False)
        self.var_fog = tk.BooleanVar(value=False)
        self.var_fog_strength = tk.StringVar()
        self.var_dof = tk.BooleanVar(value=False)
        self.var_dof_strength = tk.StringVar()
        self.var_glow = tk.StringVar()
        self.var_glow_strength = tk.StringVar()
        self.var_vdw_opacity = tk.StringVar()
        self.var_vdw_scale = tk.StringVar()
        self.var_label_font_size = tk.StringVar()
        self.var_mol_color = tk.StringVar()
        self.var_bond_color = tk.StringVar()
        self.var_bond_outline_color = tk.StringVar()
        self.var_bond_outline_width = tk.StringVar()
        self.var_atom_stroke_width = tk.StringVar()
        self.var_bond_color_by_element = tk.BooleanVar(value=False)
        self.var_bond_gradient = tk.BooleanVar(value=False)
        self.var_skeletal_label_color = tk.StringVar()
        self.var_h_scale = tk.StringVar()
        self.var_atom_gradient_strength = tk.StringVar()
        self.var_bond_gradient_strength = tk.StringVar()
        self.var_vdw_gradient_strength = tk.StringVar()
        self.var_hue_shift_factor = tk.StringVar()
        self.var_light_shift_factor = tk.StringVar()
        self.var_saturation_shift_factor = tk.StringVar()
        self.var_vdw_outline_width = tk.StringVar()
        self.var_vdw_outline_color = tk.StringVar()
        self.var_vdw_interlocking = tk.BooleanVar(value=False)
        self.var_atom_interlocking = tk.BooleanVar(value=False)
        self.var_vdw_h_scale = tk.StringVar()
        self.var_mo_outline_width = tk.StringVar()
        self.var_mo_outline_color = tk.StringVar()

        fr = ttk.LabelFrame(inner, text=_("Gradients / Fog / Glow / DoF"), padding=6)
        fr.pack(fill=tk.X, pady=(0, 3))
        _check(fr, "Radial gradients", self.var_grad)
        _check(fr, "Depth fog", self.var_fog)
        _field(fr, "Fog strength:", self.var_fog_strength, width=TINY_W)
        _check(fr, "Depth of field", self.var_dof)
        _field(fr, "DoF strength:", self.var_dof_strength, width=TINY_W)
        _field(fr, "Glow atoms:", self.var_glow, width=14)
        _field(fr, "Glow strength:", self.var_glow_strength, width=TINY_W)

        fr2 = ttk.LabelFrame(inner, text=_("VDW spheres"), padding=6)
        fr2.pack(fill=tk.X, pady=(0, 3))
        _field(fr2, "VDW opacity:", self.var_vdw_opacity, width=TINY_W)
        _field(fr2, "VDW scale:", self.var_vdw_scale, width=TINY_W)

        fr3 = ttk.LabelFrame(inner, text=_("Misc"), padding=6)
        fr3.pack(fill=tk.X, pady=(0, 3))
        _field(fr3, "Label font size:", self.var_label_font_size, width=TINY_W)
        _field(fr3, "Molecule colour:", self.var_mol_color, width=10, color=True)

        fr4 = ttk.LabelFrame(inner, text=_("Bond / atom appearance"), padding=6)
        fr4.pack(fill=tk.X, pady=(0, 3))
        _field(fr4, "Bond colour:", self.var_bond_color, width=10, color=True,
               tip="Override all bond colours")
        _field(fr4, "Bond outline:", self.var_bond_outline_color, width=10, color=True)
        _field(fr4, "Outline width:", self.var_bond_outline_width, width=TINY_W)
        _field(fr4, "Atom stroke:", self.var_atom_stroke_width, width=TINY_W,
               tip="Atom outline stroke width")
        _check(fr4, "Colour bonds by element", self.var_bond_color_by_element)
        _check(fr4, "Bond gradient (3D)", self.var_bond_gradient)
        _field(fr4, "Skeletal label colour:", self.var_skeletal_label_color, width=10, color=True)
        _field(fr4, "H scale:", self.var_h_scale, width=TINY_W,
               tip="Scale hydrogen atom radii")

        fr5 = ttk.LabelFrame(inner, text=_("Gradient strength / shifts"), padding=6)
        fr5.pack(fill=tk.X, pady=(0, 3))
        _field(fr5, "Atom gradient:", self.var_atom_gradient_strength, width=TINY_W)
        _field(fr5, "Bond gradient:", self.var_bond_gradient_strength, width=TINY_W)
        _field(fr5, "VDW gradient:", self.var_vdw_gradient_strength, width=TINY_W)
        _field(fr5, "Hue shift:", self.var_hue_shift_factor, width=TINY_W)
        _field(fr5, "Light shift:", self.var_light_shift_factor, width=TINY_W)
        _field(fr5, "Saturation shift:", self.var_saturation_shift_factor, width=TINY_W)

        fr6 = ttk.LabelFrame(inner, text=_("VDW outline / interlocking"), padding=6)
        fr6.pack(fill=tk.X, pady=(0, 3))
        _field(fr6, "VDW outline width:", self.var_vdw_outline_width, width=TINY_W)
        _field(fr6, "VDW outline colour:", self.var_vdw_outline_color, width=10, color=True)
        _check(fr6, "VDW interlocking", self.var_vdw_interlocking)
        _check(fr6, "Atom interlocking", self.var_atom_interlocking)
        _field(fr6, "VDW H scale:", self.var_vdw_h_scale, width=TINY_W)

        fr7 = ttk.LabelFrame(inner, text=_("MO outline"), padding=6)
        fr7.pack(fill=tk.X, pady=(0, 3))
        _field(fr7, "MO outline width:", self.var_mo_outline_width, width=TINY_W)
        _field(fr7, "MO outline colour:", self.var_mo_outline_color, width=10, color=True)

    # ------------------------------------------------------------- display
    def _fill_display(self):
        inner = self.tab_display.inner
        self.var_hy = tk.BooleanVar(value=False)
        self.var_hy_atoms = tk.StringVar()
        self.var_no_hy = tk.BooleanVar(value=False)
        self.var_bo = tk.BooleanVar(value=False)
        self.var_hide_bonds = tk.BooleanVar(value=False)
        self.var_haptic = tk.BooleanVar(value=False)
        self.var_unbond = tk.StringVar()
        self.var_bond = tk.StringVar()
        self.var_idx = tk.StringVar(value="")
        self.var_vdw_indices = tk.StringVar()
        self.var_only = tk.StringVar()
        self.var_exclude = tk.StringVar()

        fr = ttk.LabelFrame(inner, text=_("Hydrogens / bonds"), padding=6)
        fr.pack(fill=tk.X, pady=(0, 3))
        _check(fr, "Show all H", self.var_hy)
        _field(fr, "Show H atoms:", self.var_hy_atoms, width=ENTRY_W,
               tip='Show only these H atoms, e.g. "1-5,8" (overrides "Show all H")')
        _check(fr, "Hide all H", self.var_no_hy)
        _check(fr, "Show bond orders", self.var_bo)
        _check(fr, "Hide all bonds", self.var_hide_bonds)
        _check(fr, "Haptic (pi->centroid)", self.var_haptic)
        _field(fr, "Unbond rules:", self.var_unbond, width=ENTRY_W)
        _field(fr, "Force bonds:", self.var_bond, width=ENTRY_W)

        fr2 = ttk.LabelFrame(inner, text=_("Indices / VdW / filters"), padding=6)
        fr2.pack(fill=tk.X, pady=(0, 3))
        _combo(fr2, "Index labels:", self.var_idx, ["", "sn", "s", "n"], width=8)
        _field(fr2, "VDW atoms:", self.var_vdw_indices, width=ENTRY_W)
        _field(fr2, "Only atoms:", self.var_only, width=ENTRY_W)
        _field(fr2, "Exclude atoms:", self.var_exclude, width=ENTRY_W)

    # ------------------------------------------------------------- orient
    def _fill_orient(self):
        inner = self.tab_orient.inner
        self.var_orient = tk.StringVar(value="")
        self.var_ref = tk.StringVar()
        self.var_interactive = tk.BooleanVar(value=False)
        self.var_viewer = tk.StringVar(value="vmol")

        fr = ttk.LabelFrame(inner, text=_("Orientation"), padding=6)
        fr.pack(fill=tk.X, pady=(0, 3))
        _combo(fr, "Auto-orient:", self.var_orient, ["", "true", "false"], width=10)
        _field(fr, "Reference file:", self.var_ref, width=ENTRY_W)
        _button_row(fr, [(_("Browse…"), self._browse_ref, BROWSE_W)])
        _check(fr, "Interactive viewer (-I)", self.var_interactive)
        _combo(fr, "Viewer backend:", self.var_viewer, ["vmol", "ase"], width=10,
               tip="Interactive viewer implementation")

    def _browse_ref(self):
        path = filedialog.askopenfilename(title=_("Orientation reference XYZ"), filetypes=[("XYZ files", "*.xyz"), ALL_FILES])
        if path:
            self.var_ref.set(path)

    # ------------------------------------------------------------- ts/nci
    def _fill_tsnci(self):
        inner = self.tab_tsnci.inner
        self.var_ts_detect = tk.BooleanVar(value=False)
        self.var_nci_detect = tk.BooleanVar(value=False)
        self.var_ts_frame = tk.StringVar(value="0")
        self.var_ts_color = tk.StringVar()
        self.var_ts_element = tk.BooleanVar(value=False)
        self.var_ts_dash = tk.StringVar()
        self.var_ts_width = tk.StringVar()
        self.var_ts_bonds = tk.StringVar()
        self.var_nci_color = tk.StringVar()
        self.var_nci_element = tk.BooleanVar(value=False)
        self.var_nci_dash = tk.StringVar()
        self.var_nci_width = tk.StringVar()
        self.var_nci_bonds = tk.StringVar()

        fr = ttk.LabelFrame(inner, text=_("TS / NCI detection"), padding=6)
        fr.pack(fill=tk.X, pady=(0, 3))
        _check(fr, "Detect TS bonds", self.var_ts_detect)
        _check(fr, "Detect NCI", self.var_nci_detect)
        _field(fr, "TS frame:", self.var_ts_frame, width=TINY_W)
        _field(fr, "TS colour:", self.var_ts_color, width=8, color=True)
        _check(fr, "TS element colours", self.var_ts_element)
        _field(fr, "TS dash (len,gap):", self.var_ts_dash, width=12)
        _field(fr, "TS width:", self.var_ts_width, width=TINY_W)
        _field(fr, "TS bonds (manual):", self.var_ts_bonds, width=ENTRY_W)
        _field(fr, "NCI colour:", self.var_nci_color, width=8, color=True)
        _check(fr, "NCI element colours", self.var_nci_element)
        _field(fr, "NCI dash (len,gap):", self.var_nci_dash, width=12)
        _field(fr, "NCI width:", self.var_nci_width, width=TINY_W)
        _field(fr, "NCI bonds (manual):", self.var_nci_bonds, width=ENTRY_W)

    # ------------------------------------------------------------- gif
    def _fill_gif(self):
        inner = self.tab_gif.inner
        self.var_gif_rot = tk.BooleanVar(value=False)
        self.var_gif_bounce = tk.BooleanVar(value=False)
        self.var_gif_trj = tk.BooleanVar(value=False)
        self.var_gif_ts = tk.BooleanVar(value=False)
        self.var_gif_diffuse = tk.BooleanVar(value=False)
        self.var_gif_rot_axis = tk.StringVar(value="y")
        self.var_bounce_deg = tk.StringVar(value="50")
        self.var_bounce_axis = tk.StringVar(value="y")
        self.var_rot_frames = tk.StringVar(value="120")
        self.var_gif_fps = tk.StringVar(value="10")
        self.var_trj_bonds = tk.BooleanVar(value=False)
        self.var_detect_nci = tk.BooleanVar(value=False)
        self.var_vib_frames = tk.StringVar()
        self.var_diffuse_frames = tk.StringVar(value="60")
        self.var_diffuse_noise = tk.StringVar(value="0.3")
        self.var_diffuse_bonds = tk.StringVar(value="fade")
        self.var_diffuse_reverse = tk.BooleanVar(value=True)
        self.var_diffuse_rot = tk.StringVar(value="180")
        self.var_anchor = tk.StringVar()

        fr = ttk.LabelFrame(inner, text=_("GIF mode"), padding=6)
        fr.pack(fill=tk.X, pady=(0, 3))
        _check(fr, "Rotate", self.var_gif_rot,
               tip="Rotation GIF (combinable with TS vibration)")
        _check(fr, "Bounce", self.var_gif_bounce,
               tip="Bounce rotation GIF (combinable with TS vibration)")
        _check(fr, "Trajectory", self.var_gif_trj,
               tip="Multi-frame trajectory GIF")
        _check(fr, "TS vibration", self.var_gif_ts,
               tip="TS vibration GIF (graphRC)")
        _check(fr, "Diffuse", self.var_gif_diffuse,
               tip="Diffuse / assembly GIF")
        for _var in (self.var_gif_rot, self.var_gif_bounce, self.var_gif_trj,
                     self.var_gif_ts, self.var_gif_diffuse):
            _var.trace_add("write", lambda *_: self._on_gif_mode_change())

        self.fr_rot = ttk.LabelFrame(inner, text=_("Rotation / bounce"), padding=6)
        _combo(self.fr_rot, "Axis:", self.var_gif_rot_axis, ROTATION_AXES, width=8)
        _field(self.fr_rot, "Bounce deg:", self.var_bounce_deg, width=TINY_W)
        _combo(self.fr_rot, "Bounce axis:", self.var_bounce_axis, ROTATION_AXES, width=8)
        _field(self.fr_rot, "Frames:", self.var_rot_frames, width=TINY_W)
        _field(self.fr_rot, "FPS:", self.var_gif_fps, width=TINY_W)

        self.fr_trj = ttk.LabelFrame(inner, text=_("Trajectory / TS / Diffuse"), padding=6)
        _check(self.fr_trj, "Re-detect bonds/frame", self.var_trj_bonds)
        _check(self.fr_trj, "Detect NCI/frame", self.var_detect_nci)
        _field(self.fr_trj, "Vib frames:", self.var_vib_frames, width=TINY_W)
        _field(self.fr_trj, "Diffuse frames:", self.var_diffuse_frames, width=TINY_W)
        _field(self.fr_trj, "Diffuse noise:", self.var_diffuse_noise, width=TINY_W)
        _combo(self.fr_trj, "Diffuse bonds:", self.var_diffuse_bonds, ["fade", "show", "hide"], width=9)
        _check(self.fr_trj, "Reverse diffuse", self.var_diffuse_reverse)
        _field(self.fr_trj, "Diffuse rot:", self.var_diffuse_rot, width=TINY_W)
        _field(self.fr_trj, "Anchor atoms:", self.var_anchor, width=ENTRY_W)

        self._on_gif_mode_change()

    def _on_gif_mode_change(self):
        show_rot = self.var_gif_rot.get() or self.var_gif_bounce.get()
        show_trj = (self.var_gif_trj.get() or self.var_gif_ts.get()
                    or self.var_gif_diffuse.get())
        if show_rot:
            self.fr_rot.pack(fill=tk.X, pady=(0, 5), before=self.fr_trj)
        else:
            self.fr_rot.pack_forget()
        if show_trj:
            self.fr_trj.pack(fill=tk.X, pady=(0, 3))
        else:
            self.fr_trj.pack_forget()

    # ------------------------------------------------------------- surface
    def _fill_surface(self):
        inner = self.tab_surface.inner
        self.var_mo = tk.BooleanVar(value=False)
        self.var_dens = tk.BooleanVar(value=False)
        self.var_esp = tk.StringVar()
        self.var_nci = tk.StringVar()
        self.var_iso = tk.StringVar()
        self.var_surface_style = tk.StringVar(value="solid")
        self.var_mo_pos_color = tk.StringVar()
        self.var_mo_neg_color = tk.StringVar()
        self.var_mo_blur = tk.StringVar()
        self.var_mo_upsample = tk.StringVar()
        self.var_flat_mo = tk.BooleanVar(value=False)
        self.var_dens_color = tk.StringVar()
        self.var_nci_mode = tk.StringVar(value="avg")
        self.var_nci_cutoff = tk.StringVar()

        fr = ttk.LabelFrame(inner, text=_("Surfaces (cube input)"), padding=6)
        fr.pack(fill=tk.X, pady=(0, 3))
        _check(fr, "MO lobes", self.var_mo)
        _check(fr, "Density", self.var_dens)
        _field(fr, "ESP cube:", self.var_esp, width=ENTRY_W)
        _button_row(fr, [(_("Browse…"), self._browse_esp, BROWSE_W)])
        _field(fr, "NCI surface cube:", self.var_nci, width=ENTRY_W)
        _button_row(fr, [(_("Browse…"), self._browse_nci, BROWSE_W)])
        _field(fr, "Isovalue:", self.var_iso, width=TINY_W)
        _combo(fr, "Surface style:", self.var_surface_style, SURFACE_STYLES, width=9)

        fr2 = ttk.LabelFrame(inner, text=_("Colours / options"), padding=6)
        fr2.pack(fill=tk.X, pady=(0, 3))
        _field(fr2, "MO pos:", self.var_mo_pos_color, width=TINY_W, color=True)
        _field(fr2, "MO neg:", self.var_mo_neg_color, width=TINY_W, color=True)
        _field(fr2, "MO blur:", self.var_mo_blur, width=TINY_W)
        _field(fr2, "MO upsample:", self.var_mo_upsample, width=TINY_W)
        _check(fr2, "Flat MO", self.var_flat_mo)
        _field(fr2, "Density colour:", self.var_dens_color, width=TINY_W, color=True)
        _combo(fr2, "NCI mode:", self.var_nci_mode, NCI_MODES, width=9)
        _field(fr2, "NCI cutoff:", self.var_nci_cutoff, width=TINY_W)

    def _browse_esp(self):
        path = filedialog.askopenfilename(title=_("ESP cube"), filetypes=[("Cube files", "*.cube *.cub"), ALL_FILES])
        if path:
            self.var_esp.set(path)

    def _browse_nci(self):
        path = filedialog.askopenfilename(title=_("NCI cube"), filetypes=[("Cube files", "*.cube *.cub"), ALL_FILES])
        if path:
            self.var_nci.set(path)

    # ------------------------------------------------------------ overlay
    def _fill_overlay(self):
        inner = self.tab_overlay.inner
        self.var_overlay = tk.StringVar()
        self.var_overlay_color = tk.StringVar()
        self.var_opacity = tk.StringVar()
        self.var_align_atoms = tk.StringVar()
        self.var_auto_align = tk.StringVar(value="")
        self.var_overlay_unbond = tk.StringVar()
        self.var_overlay_bond = tk.StringVar()
        self.var_overlay_show = tk.StringVar()
        self.var_overlay_atom_scale = tk.StringVar()
        self.var_overlay_bond_width = tk.StringVar()
        self.var_overlay_ts = tk.BooleanVar(value=False)
        self.var_overlay_ts_bond = tk.StringVar()

        fr = ttk.LabelFrame(inner, text=_("Structural overlay"), padding=6)
        fr.pack(fill=tk.X, pady=(0, 3))
        _field(fr, "Overlay file:", self.var_overlay, width=ENTRY_W)
        _button_row(fr, [(_("Browse…"), self._browse_overlay, BROWSE_W)])
        _field(fr, "Overlay colour:", self.var_overlay_color, width=8, color=True)
        _field(fr, "Opacity:", self.var_opacity, width=TINY_W)
        _field(fr, "Align atoms:", self.var_align_atoms, width=ENTRY_W)
        _combo(fr, "Auto-align:", self.var_auto_align, ["", "true", "false"], width=10)

        fr2 = ttk.LabelFrame(inner, text=_("Overlay styling"), padding=6)
        fr2.pack(fill=tk.X, pady=(0, 3))
        _field(fr2, "Overlay unbond:", self.var_overlay_unbond, width=ENTRY_W,
               tip="Overlay-only bond-hide rules")
        _field(fr2, "Overlay bonds:", self.var_overlay_bond, width=ENTRY_W,
               tip="Force-show / add overlay bonds")
        _field(fr2, "Overlay show:", self.var_overlay_show, width=ENTRY_W,
               tip="Visibility filter for overlay atoms")
        _field(fr2, "Overlay atom scale:", self.var_overlay_atom_scale, width=TINY_W)
        _field(fr2, "Overlay bond width:", self.var_overlay_bond_width, width=TINY_W)
        _check(fr2, "Overlay TS detection", self.var_overlay_ts)
        _field(fr2, "Overlay TS bonds:", self.var_overlay_ts_bond, width=ENTRY_W)

    def _browse_overlay(self):
        path = filedialog.askopenfilename(title=_("Overlay molecule"), filetypes=[INPUT_EXTENSIONS, ALL_FILES])
        if path:
            self.var_overlay.set(path)

    # ------------------------------------------------------------- annot
    def _fill_annot(self):
        inner = self.tab_annot.inner
        self.var_labels = tk.StringVar()
        self.var_label_file = tk.StringVar()
        self.var_stereo = tk.StringVar(value="off")
        self.var_stereo_style = tk.StringVar(value="atom")
        self.var_cmap = tk.StringVar()
        self.var_cmap_range = tk.StringVar()
        self.var_cmap_palette = tk.StringVar()
        self.var_cmap_symm = tk.BooleanVar(value=False)
        self.var_cbar = tk.BooleanVar(value=False)

        fr = ttk.LabelFrame(inner, text=_("Annotations"), padding=6)
        fr.pack(fill=tk.X, pady=(0, 3))
        _field(fr, "Custom labels (-l):", self.var_labels, width=ENTRY_W)
        _field(fr, "Label file:", self.var_label_file, width=ENTRY_W)
        _button_row(fr, [(_("Browse…"), self._browse_label_file, BROWSE_W)])
        _combo(fr, "Stereo class:", self.var_stereo, ["off", "all"] + STEREO_CLASSES, width=10)
        _combo(fr, "Stereo style:", self.var_stereo_style, ["atom", "label"], width=9)
        _field(fr, "Cmap file:", self.var_cmap, width=ENTRY_W)
        _button_row(fr, [(_("Browse…"), self._browse_cmap, BROWSE_W)])
        _field(fr, "Cmap range:", self.var_cmap_range, width=ENTRY_W)
        _field(fr, "Cmap palette:", self.var_cmap_palette, width=ENTRY_W)
        _check(fr, "Symmetric cmap", self.var_cmap_symm)
        _check(fr, "Colorbar", self.var_cbar)

    # ------------------------------------------------------------- vector
    def _fill_vector(self):
        inner = self.tab_vector.inner
        self.var_vector = tk.StringVar()
        self.var_vector_scale = tk.StringVar()
        self.var_vector_color = tk.StringVar()

        fr = ttk.LabelFrame(inner, text=_("3D vector arrows"), padding=6)
        fr.pack(fill=tk.X, pady=(0, 3))
        _field(fr, "Vector file:", self.var_vector, width=ENTRY_W,
               tip="File listing 3D vectors (or displacement field)")
        _button_row(fr, [(_("Browse…"), self._browse_vector, BROWSE_W)])
        _field(fr, "Vector scale:", self.var_vector_scale, width=TINY_W)
        _field(fr, "Vector colour:", self.var_vector_color, width=10, color=True)

    def _browse_vector(self):
        path = filedialog.askopenfilename(title=_("Vector file"), filetypes=[ALL_FILES])
        if path:
            self.var_vector.set(path)

    def _browse_label_file(self):
        path = filedialog.askopenfilename(title=_("Annotation file"), filetypes=[("Text files", "*.txt"), ALL_FILES])
        if path:
            self.var_label_file.set(path)

    def _browse_cmap(self):
        path = filedialog.askopenfilename(title=_("Colormap file"), filetypes=[("Text files", "*.txt"), ALL_FILES])
        if path:
            self.var_cmap.set(path)

    # -------------------------------------------------------- highlight
    def _fill_highlight(self):
        inner = self.tab_highlight.inner
        self.var_highlight = tk.StringVar()
        self.var_radius_scale = tk.StringVar()
        self.var_atom_opacity = tk.StringVar()
        self.var_regions = tk.StringVar()

        fr = ttk.LabelFrame(inner, text=_("Highlights"), padding=6)
        fr.pack(fill=tk.X, pady=(0, 3))
        _field(fr, "Highlight groups:", self.var_highlight, width=ENTRY_W,
               tip='"1-5,8 red; 9-12 blue". Groups separated by ";".')

        fr2 = ttk.LabelFrame(inner, text=_("Radius scale"), padding=6)
        fr2.pack(fill=tk.X, pady=(0, 3))
        _field(fr2, "spec:factor", self.var_radius_scale, width=ENTRY_W,
               tip='e.g. "1-5,8:2.0", "M:1.5", or multiple groups "N,O:1.4; H:0.8"')

        fr3 = ttk.LabelFrame(inner, text=_("Atom opacity"), padding=6)
        fr3.pack(fill=tk.X, pady=(0, 3))
        _field(fr3, "index:value", self.var_atom_opacity, width=ENTRY_W,
               tip='e.g. "1-5:0.3; M:0.5"')

        fr4 = ttk.LabelFrame(inner, text=_("Style regions"), padding=6)
        fr4.pack(fill=tk.X, pady=(0, 3))
        _field(fr4, "atoms:preset", self.var_regions, width=ENTRY_W,
               tip='e.g. "1-6:flat; Fe:tube"')

    # ---------------------------------------------------------- hull / pore
    def _fill_hullpore(self):
        inner = self.tab_hullpore.inner
        self.var_hull = tk.StringVar()
        self.var_hull_color = tk.StringVar()
        self.var_hull_opacity = tk.StringVar()
        self.var_hull_color_type = tk.StringVar(value="type")
        self.var_hull_edge = tk.BooleanVar(value=True)
        self.var_hull_edge_width_ratio = tk.StringVar()
        self.var_pore = tk.BooleanVar(value=False)
        self.var_pore_color = tk.StringVar()
        self.var_pore_opacity = tk.StringVar()
        self.var_ring_max_size = tk.StringVar(value="100")
        self.var_ring_min_size = tk.StringVar(value="3")
        self.var_face_planarity = tk.StringVar(value="0.25")

        fr = ttk.LabelFrame(inner, text=_("Convex hull"), padding=6)
        fr.pack(fill=tk.X, pady=(0, 3))
        _field(fr, "Hull:", self.var_hull, width=ENTRY_W,
               tip='"rings", "faces", "pores", or atom index ranges (e.g. "1-6"; "1-6;7-12")')
        _field(fr, "Hull colour:", self.var_hull_color, width=10, color=True)
        _field(fr, "Hull opacity:", self.var_hull_opacity, width=TINY_W)
        _combo(fr, "Hull colour type:", self.var_hull_color_type,
               ["type", "size", "env"], width=10)
        _check(fr, "Hull edges", self.var_hull_edge)
        _field(fr, "Edge width ratio:", self.var_hull_edge_width_ratio, width=TINY_W)

        fr2 = ttk.LabelFrame(inner, text=_("Pores / rings"), padding=6)
        fr2.pack(fill=tk.X, pady=(0, 3))
        _check(fr2, "Draw pores", self.var_pore)
        _field(fr2, "Pore colour:", self.var_pore_color, width=10, color=True)
        _field(fr2, "Pore opacity:", self.var_pore_opacity, width=TINY_W)
        _field(fr2, "Ring max size:", self.var_ring_max_size, width=TINY_W)
        _field(fr2, "Ring min size:", self.var_ring_min_size, width=TINY_W)
        _field(fr2, "Face planarity:", self.var_face_planarity, width=TINY_W)

    # ------------------------------------------------------------- crystal
    def _fill_crystal(self):
        inner = self.tab_crystal.inner
        self.var_cell = tk.BooleanVar(value=False)
        self.var_no_cell = tk.BooleanVar(value=False)
        self.var_ghosts = tk.BooleanVar(value=False)
        self.var_axes = tk.BooleanVar(value=False)
        self.var_axis = tk.StringVar()
        self.var_supercell_m = tk.StringVar(value="1")
        self.var_supercell_n = tk.StringVar(value="1")
        self.var_supercell_l = tk.StringVar(value="1")
        self.var_cell_color = tk.StringVar()
        self.var_cell_width = tk.StringVar()
        self.var_ghost_opacity = tk.StringVar()

        fr = ttk.LabelFrame(inner, text=_("Unit cell / periodic"), padding=6)
        fr.pack(fill=tk.X, pady=(0, 3))
        _check(fr, "Draw unit cell", self.var_cell)
        _check(fr, "No cell", self.var_no_cell)
        _check(fr, "Ghosts", self.var_ghosts)
        _check(fr, "Axes", self.var_axes)
        _field(fr, "Axis (HKL):", self.var_axis, width=TINY_W)
        _field(fr, "Supercell M:", self.var_supercell_m, width=TINY_W)
        _field(fr, "Supercell N:", self.var_supercell_n, width=TINY_W)
        _field(fr, "Supercell L:", self.var_supercell_l, width=TINY_W)
        _field(fr, "Cell colour:", self.var_cell_color, width=TINY_W, color=True)
        _field(fr, "Cell width:", self.var_cell_width, width=TINY_W)
        _field(fr, "Ghost opacity:", self.var_ghost_opacity, width=TINY_W)

    # ------------------------------------------------------------- measure
    def _fill_measure(self):
        inner = self.tab_measure.inner
        self.var_measure_d = tk.BooleanVar(value=False)
        self.var_measure_a = tk.BooleanVar(value=False)
        self.var_measure_t = tk.BooleanVar(value=False)

        fr = ttk.LabelFrame(inner, text=_("Geometry measurements"), padding=6)
        fr.pack(fill=tk.X, pady=(0, 3))
        _check(fr, "Distances (d)", self.var_measure_d)
        _check(fr, "Angles (a)", self.var_measure_a)
        _check(fr, "Dihedrals (t)", self.var_measure_t)

    # =====================================================================
    # Render / Save actions
    # =====================================================================

    def _collect_params(self) -> dict:
        input_path = self.var_input.get().strip()
        sel_path = self._tree_selected_path()
        if not input_path and sel_path:
            input_path = sel_path
            self.var_input.set(input_path)
        if not input_path:
            children = self.tree.get_children()
            if children:
                tags = self.tree.item(children[0], "tags")
                if tags:
                    input_path = tags[0]
                    self.var_input.set(input_path)

        output = self.var_output.get().strip()
        output_format = self.var_out_fmt.get()
        smiles_string = self.var_smiles.get().strip()

        p: dict = {
            "input_path": input_path,
            "output": output,
            "output_format": output_format,
            "smiles_string": smiles_string,
            "smiles": bool(smiles_string),
            "charge": _pint(self.var_charge.get()),
            "multiplicity": _pint(self.var_mult.get()),
            "config": self.var_preset.get() or "default",
            "canvas_size": self.var_canvas_size.get(),
            "atom_scale": self.var_atom_scale.get(),
            "bond_width": self.var_bond_width.get(),
            "background": self.var_background.get(),
            "transparent": self.var_transparent.get(),
            "gradient": self.var_grad.get(),
            "fog": self.var_fog.get(),
            "fog_strength": self.var_fog_strength.get(),
            "dof": self.var_dof.get(),
            "dof_strength": self.var_dof_strength.get(),
            "glow": self.var_glow.get(),
            "glow_strength": self.var_glow_strength.get(),
            "vdw_opacity": self.var_vdw_opacity.get(),
            "vdw_scale": self.var_vdw_scale.get(),
            "label_font_size": self.var_label_font_size.get(),
            "mol_color": self.var_mol_color.get(),
            "hy": self.var_hy.get(),
            "hy_atoms": self.var_hy_atoms.get(),
            "no_hy": self.var_no_hy.get(),
            "bo": self.var_bo.get(),
            "hide_bonds": self.var_hide_bonds.get(),
            "haptic": self.var_haptic.get(),
            "unbond": self.var_unbond.get(),
            "bond": self.var_bond.get(),
            "idx": self.var_idx.get(),
            "vdw_indices": self.var_vdw_indices.get(),
            "only": self.var_only.get(),
            "exclude": self.var_exclude.get(),
            "orient": self.var_orient.get(),
            "ref": self.var_ref.get(),
            "interactive": self.var_interactive.get(),
            "ts_detect": self.var_ts_detect.get(),
            "nci_detect": self.var_nci_detect.get(),
            "ts_frame": self.var_ts_frame.get(),
            "ts_color": self.var_ts_color.get(),
            "ts_element": self.var_ts_element.get(),
            "ts_dash": self.var_ts_dash.get(),
            "ts_width": self.var_ts_width.get(),
            "ts_bonds": self.var_ts_bonds.get(),
            "nci_color": self.var_nci_color.get(),
            "nci_element": self.var_nci_element.get(),
            "nci_dash": self.var_nci_dash.get(),
            "nci_width": self.var_nci_width.get(),
            "nci_bonds": self.var_nci_bonds.get(),
            "gif_rot": self.var_gif_rot.get(),
            "gif_bounce": self.var_gif_bounce.get(),
            "gif_trj": self.var_gif_trj.get(),
            "gif_ts": self.var_gif_ts.get(),
            "gif_diffuse": self.var_gif_diffuse.get(),
            "gif_rot_axis": self.var_gif_rot_axis.get(),
            "bounce_deg": self.var_bounce_deg.get(),
            "bounce_axis": self.var_bounce_axis.get(),
            "rot_frames": self.var_rot_frames.get(),
            "gif_fps": self.var_gif_fps.get(),
            "trj_bonds": self.var_trj_bonds.get(),
            "detect_nci": self.var_detect_nci.get(),
            "vib_frames": self.var_vib_frames.get(),
            "diffuse_frames": self.var_diffuse_frames.get(),
            "diffuse_noise": self.var_diffuse_noise.get(),
            "diffuse_bonds": self.var_diffuse_bonds.get(),
            "diffuse_reverse": self.var_diffuse_reverse.get(),
            "diffuse_rot": self.var_diffuse_rot.get(),
            "anchor": self.var_anchor.get(),
            "mo": self.var_mo.get(),
            "dens": self.var_dens.get(),
            "esp": self.var_esp.get(),
            "nci": self.var_nci.get(),
            "iso": self.var_iso.get(),
            "surface_style": self.var_surface_style.get(),
            "mo_pos_color": self.var_mo_pos_color.get(),
            "mo_neg_color": self.var_mo_neg_color.get(),
            "mo_blur": self.var_mo_blur.get(),
            "mo_upsample": self.var_mo_upsample.get(),
            "flat_mo": self.var_flat_mo.get(),
            "dens_color": self.var_dens_color.get(),
            "nci_mode": self.var_nci_mode.get(),
            "nci_cutoff": self.var_nci_cutoff.get(),
            "overlay": self.var_overlay.get(),
            "overlay_color": self.var_overlay_color.get(),
            "opacity": self.var_opacity.get(),
            "align_atoms": self.var_align_atoms.get(),
            "auto_align": self.var_auto_align.get(),
            "cell": self.var_cell.get(),
            "no_cell": self.var_no_cell.get(),
            "ghosts": self.var_ghosts.get(),
            "axes": self.var_axes.get(),
            "axis": self.var_axis.get(),
            "supercell_m": self.var_supercell_m.get(),
            "supercell_n": self.var_supercell_n.get(),
            "supercell_l": self.var_supercell_l.get(),
            "cell_color": self.var_cell_color.get(),
            "cell_width": self.var_cell_width.get(),
            "ghost_opacity": self.var_ghost_opacity.get(),
            "labels": self.var_labels.get(),
            "label_file": self.var_label_file.get(),
            "stereo": self.var_stereo.get(),
            "stereo_style": self.var_stereo_style.get(),
            "cmap": self.var_cmap.get(),
            "cmap_range": self.var_cmap_range.get(),
            "cmap_palette": self.var_cmap_palette.get(),
            "cmap_symm": self.var_cmap_symm.get(),
            "cbar": self.var_cbar.get(),
            "highlight": self.var_highlight.get(),
            "radius_scale": self.var_radius_scale.get(),
            "atom_opacity": self.var_atom_opacity.get(),
            "regions": self.var_regions.get(),
            "measure_d": self.var_measure_d.get(),
            "measure_a": self.var_measure_a.get(),
            "measure_t": self.var_measure_t.get(),
            # --- loading ---
            "kekule": self.var_kekule.get(),
            "rebuild": self.var_rebuild.get(),
            "bohr": self.var_bohr.get(),
            "mol_frame": self.var_mol_frame.get(),
            "quick": self.var_quick.get(),
            "ensemble": self.var_ensemble.get(),
            "ensemble_color": self.var_ensemble_color.get(),
            # --- fine styling ---
            "bond_color": self.var_bond_color.get(),
            "bond_outline_color": self.var_bond_outline_color.get(),
            "bond_outline_width": self.var_bond_outline_width.get(),
            "atom_stroke_width": self.var_atom_stroke_width.get(),
            "bond_color_by_element": self.var_bond_color_by_element.get(),
            "bond_gradient": self.var_bond_gradient.get(),
            "skeletal_label_color": self.var_skeletal_label_color.get(),
            "h_scale": self.var_h_scale.get(),
            "atom_gradient_strength": self.var_atom_gradient_strength.get(),
            "bond_gradient_strength": self.var_bond_gradient_strength.get(),
            "vdw_gradient_strength": self.var_vdw_gradient_strength.get(),
            "hue_shift_factor": self.var_hue_shift_factor.get(),
            "light_shift_factor": self.var_light_shift_factor.get(),
            "saturation_shift_factor": self.var_saturation_shift_factor.get(),
            "vdw_outline_width": self.var_vdw_outline_width.get(),
            "vdw_outline_color": self.var_vdw_outline_color.get(),
            "vdw_interlocking": self.var_vdw_interlocking.get(),
            "atom_interlocking": self.var_atom_interlocking.get(),
            "vdw_h_scale": self.var_vdw_h_scale.get(),
            "mo_outline_width": self.var_mo_outline_width.get(),
            "mo_outline_color": self.var_mo_outline_color.get(),
            # --- interactive viewer backend ---
            "viewer": self.var_viewer.get(),
            # --- overlay styling ---
            "overlay_unbond": self.var_overlay_unbond.get(),
            "overlay_bond": self.var_overlay_bond.get(),
            "overlay_show": self.var_overlay_show.get(),
            "overlay_atom_scale": self.var_overlay_atom_scale.get(),
            "overlay_bond_width": self.var_overlay_bond_width.get(),
            "overlay_ts": self.var_overlay_ts.get(),
            "overlay_ts_bond": self.var_overlay_ts_bond.get(),
            # --- vectors ---
            "vector": self.var_vector.get(),
            "vector_scale": self.var_vector_scale.get(),
            "vector_color": self.var_vector_color.get(),
            # --- convex hull / pores ---
            "hull": self.var_hull.get(),
            "hull_color": self.var_hull_color.get(),
            "hull_opacity": self.var_hull_opacity.get(),
            "hull_color_type": self.var_hull_color_type.get(),
            "hull_edge": self.var_hull_edge.get(),
            "hull_edge_width_ratio": self.var_hull_edge_width_ratio.get(),
            "pore": self.var_pore.get(),
            "pore_color": self.var_pore_color.get(),
            "pore_opacity": self.var_pore_opacity.get(),
            "ring_max_size": self.var_ring_max_size.get(),
            "ring_min_size": self.var_ring_min_size.get(),
            "face_planarity": self.var_face_planarity.get(),
        }
        return p

    def _on_render(self):
        # Ignore re-entry while a render thread is still running.
        if getattr(self, "_thread", None) is not None and self._thread.is_alive():
            return
        params = self._collect_params()
        if not params.get("input_path") and not params.get("smiles_string"):
            messagebox.showwarning(_("xyzrender GUI"), _("Please provide an input file or a SMILES string."))
            return
        # Render only previews — do not write to disk yet.  Save writes the file.
        params["output"] = None
        params["output_format"] = self.var_out_fmt.get()

        self.btn_render.configure(state=tk.DISABLED)
        self.btn_save.configure(state=tk.DISABLED)
        self.btn_open.configure(state=tk.DISABLED)
        self.var_rendering.set(_("Rendering…"))
        self.progress.start(12)
        self.status_var.set(_("Rendering in progress…"))
        # self.log_message(">>> " + _("Starting render…"))

        self._rendered_svg = None
        self._thread = RenderThread(params, self._on_render_done, result_queue=self._result_queue)
        self._thread.start()

    def _on_render_done(self, thread: RenderThread):
        self.progress.stop()
        self.btn_render.configure(state=tk.NORMAL)
        self.var_rendering.set(_("Idle"))
        if thread.error:
            self.status_var.set(_("Render failed"))
            # self.log_message("!!! " + _("ERROR: ") + repr(thread.error))
            messagebox.showerror(_("xyzrender GUI — render failed"), str(thread.error))
        else:
            self.status_var.set(_("Render complete"))
            # self.log_message(">>> " + _("Render complete."))
            if thread.result_svg is not None:
                # Static render: preview only, do not save to disk yet.
                self._rendered_svg = thread.result_svg
                self.show_preview_from_svg(thread.result_svg)
                self.btn_save.configure(state=tk.NORMAL)
                self.btn_save_toolbar.configure(state=tk.NORMAL)
                self.btn_open.configure(state=tk.DISABLED)
                self._last_output = None
            elif thread.result_path:
                # GIF preview: show the animation's first frame in the canvas.
                self.show_preview(thread.result_path)
                self.btn_save.configure(state=tk.NORMAL)
                self.btn_save_toolbar.configure(state=tk.NORMAL)
                self.btn_open.configure(state=tk.DISABLED)
                self._last_output = None
                self.status_var.set(_("Render complete"))
            if thread.result_text:
                self._show_measurements(thread.result_text)

    def _show_measurements(self, text: str):
        """Show geometry measurement output in a scrollable pop-up window."""
        win = tk.Toplevel(self)
        win.title(_("Measurements"))
        win.geometry("560x420")
        txt = tk.Text(win, wrap=tk.NONE, font=("Consolas", 9))
        yscroll = ttk.Scrollbar(win, orient=tk.VERTICAL, command=txt.yview)
        xscroll = ttk.Scrollbar(win, orient=tk.HORIZONTAL, command=txt.xview)
        txt.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        txt.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        win.rowconfigure(0, weight=1)
        win.columnconfigure(0, weight=1)
        txt.insert("1.0", text)
        txt.configure(state=tk.DISABLED)
        ttk.Button(win, text=_("Close"), command=win.destroy).grid(
            row=2, column=0, columnspan=2, pady=6)

    def _on_save(self):
        wants_gif = (self.var_gif_rot.get() or self.var_gif_bounce.get()
                     or self.var_gif_trj.get() or self.var_gif_ts.get()
                     or self.var_gif_diffuse.get())
        if self._rendered_svg is None and not wants_gif:
            messagebox.showwarning(_("xyzrender GUI"), _("Nothing to save. Render first."))
            return

        fmt = "gif" if wants_gif else self.var_out_fmt.get()
        default_name = "graphic." + fmt
        if self.var_input.get().strip():
            default_name = Path(self.var_input.get()).stem + "." + fmt

        path = filedialog.asksaveasfilename(
            title=_("Save output as"),
            defaultextension="." + fmt,
            initialfile=default_name,
            filetypes=[(fmt.upper() + " files", "*." + fmt), ALL_FILES],
        )
        if not path:
            return

        ext = Path(path).suffix.lower().lstrip(".")
        if wants_gif:
            # GIF mode always writes an animation — force a .gif path.
            if ext != "gif":
                path = str(Path(path).with_suffix(".gif"))
                ext = "gif"
        elif ext not in OUTPUT_FORMATS:
            ext = fmt
            if not Path(path).suffix:
                path = path + "." + ext

        try:
            params = self._collect_params()
            params["output"] = path
            params["output_format"] = ext

            self.btn_render.configure(state=tk.DISABLED)
            self.btn_save.configure(state=tk.DISABLED)
            self.var_rendering.set(_("Rendering…"))
            self.progress.start(12)
            self.status_var.set(_("Saving…"))
            # self.log_message(">>> " + _("Saving to ") + path)

            save_thread = RenderThread(params, self._on_save_done, result_queue=self._result_queue)
            save_thread.start()
        except Exception as exc:  # noqa: BLE001
            self.btn_render.configure(state=tk.NORMAL)
            self.btn_save.configure(state=tk.NORMAL)
            self.var_rendering.set(_("Idle"))
            self.status_var.set(_("Save failed"))
            # self.log_message("!!! " + _("ERROR: ") + repr(exc))
            messagebox.showerror(_("xyzrender GUI — save failed"), str(exc))

    def _on_save_done(self, thread: RenderThread):
        self.progress.stop()
        self.btn_render.configure(state=tk.NORMAL)
        self.btn_save.configure(state=tk.NORMAL)
        self.var_rendering.set(_("Idle"))
        if thread.error:
            self.status_var.set(_("Save failed"))
            # self.log_message("!!! " + _("ERROR: ") + repr(thread.error))
            messagebox.showerror(_("xyzrender GUI — save failed"), str(thread.error))
        else:
            self.status_var.set(_("Render complete"))
            # self.log_message(">>> " + _("Render complete.") + "  " + _("Output: ") + thread.result_path)
            self._last_output = thread.result_path
            if thread.result_path and Path(thread.result_path).exists():
                self.btn_open.configure(state=tk.NORMAL)
                messagebox.showinfo(_("xyzrender GUI"), _("Render complete.\n") + _("Output: ") + thread.result_path)
            else:
                self.btn_open.configure(state=tk.DISABLED)
                messagebox.showerror(_("xyzrender GUI — save failed"), _("File was not created: ") + str(thread.result_path))


def main():
    app = XyzrenderGUI()
    app.mainloop()


if __name__ == "__main__":
    # GIF rendering runs frames through multiprocessing.Pool().  In the
    # frozen exe every pool worker (and the resource_tracker helper)
    # re-launches this executable with special argv; freeze_support()
    # diverts such children into worker code.  Without this call each
    # child would run main() and open a new GUI window per CPU core.
    import multiprocessing

    multiprocessing.freeze_support()
    main()
