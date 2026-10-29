"""Export SVG to raster/vector formats.

PNG rendering prefers **resvg-py** — it supports SVG filter primitives
(``feGaussianBlur``, ``feTurbulence``, etc.) that cairosvg silently ignores.
PDF rendering uses cairosvg (resvg-py has no PDF support).
"""

from __future__ import annotations

from functools import lru_cache

_SVG_BASE_DPI = 96  # CSS/SVG spec: 1px = 1/96 inch


@lru_cache(maxsize=1)
def _has_resvg() -> bool:
    try:
        from resvg_py import svg_to_bytes  # noqa: F401
    except ImportError:
        return False
    return True


def svg_to_png_bytes(svg: str, *, size: int = 800) -> bytes:
    """Convert SVG string to PNG bytes at a fixed pixel size.

    Used by GIF frame rendering where exact pixel dimensions matter.
    """
    if _has_resvg():
        from resvg_py import svg_to_bytes

        return svg_to_bytes(svg_string=svg, width=size, height=size)

    import cairosvg

    return cairosvg.svg2png(bytestring=svg.encode(), output_width=size, output_height=size)


def svg_to_png(svg: str, output: str, *, size: int = 800, dpi: int = 300) -> None:
    """Convert SVG string to a PNG file.

    Higher *dpi* produces a larger image with more detail (dpi/96 zoom factor).
    """
    if _has_resvg():
        from resvg_py import svg_to_bytes

        zoom = max(1, round(dpi / _SVG_BASE_DPI))
        data = svg_to_bytes(svg_string=svg, zoom=zoom)
    else:
        import cairosvg

        data = cairosvg.svg2png(bytestring=svg.encode(), output_width=size, output_height=size, dpi=dpi)

    with open(output, "wb") as f:
        f.write(data)


def svg_to_pdf(svg: str, output: str, *, size: int = 800, dpi: int = 300) -> None:
    """Convert SVG string to PDF file.

    Prefers **cairosvg** (true vector output) when the system cairo library
    is present.  When cairo is unavailable (common on stock Windows), falls
    back to rasterising with **resvg-py** at *dpi* and wrapping the resulting
    PNG in a PDF via Pillow, so PDF export always works.
    """
    try:
        import cairosvg

        cairosvg.svg2pdf(bytestring=svg.encode(), write_to=output)
        return
    except Exception:  # noqa: BLE001 — missing cairo DLL or SVG filter issues
        pass

    # --- Raster fallback: resvg-py -> PNG -> PDF (Pillow) ---
    from io import BytesIO

    from PIL import Image

    if _has_resvg():
        from resvg_py import svg_to_bytes

        zoom = max(1, round(dpi / _SVG_BASE_DPI))
        png_data = svg_to_bytes(svg_string=svg, zoom=zoom)
    else:
        import cairosvg

        png_data = cairosvg.svg2png(bytestring=svg.encode(), output_width=size, output_height=size, dpi=dpi)

    img = Image.open(BytesIO(png_data)).convert("RGB")
    img.save(output, format="PDF", resolution=dpi)


def svg_to_tiff(svg: str, output: str, *, size: int = 800, dpi: int = 300) -> None:
    """Render SVG at target DPI and save as TIFF.

    Rasterises via resvg-py (preferred) or cairosvg, then converts the
    lossless PNG bytes to LZW-compressed TIFF via Pillow.
    """
    from io import BytesIO

    from PIL import Image

    if _has_resvg():
        from resvg_py import svg_to_bytes

        zoom = max(1, round(dpi / _SVG_BASE_DPI))
        png_data = svg_to_bytes(svg_string=svg, zoom=zoom)
    else:
        import cairosvg

        png_data = cairosvg.svg2png(bytestring=svg.encode(), output_width=size, output_height=size, dpi=dpi)

    img = Image.open(BytesIO(png_data))
    img.save(output, format="TIFF", dpi=(dpi, dpi), compression="tiff_deflate")
