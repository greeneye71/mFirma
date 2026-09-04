from __future__ import annotations

from collections.abc import Callable

from .models import PageGeometry, SignaturePlacement


PRESETS = {"top_left", "top_right", "bottom_left", "bottom_right"}


def _display_to_page_transform(
    geometry: PageGeometry,
) -> tuple[float, float, Callable[[float, float], tuple[float, float]]]:
    width, height = geometry.width, geometry.height
    llx, lly = geometry.lower_left_x, geometry.lower_left_y
    rotation = geometry.rotation % 360
    if rotation == 0:
        return width, height, lambda x, y: (llx + x, lly + y)
    if rotation == 90:
        return height, width, lambda x, y: (llx + width - y, lly + x)
    if rotation == 180:
        return width, height, lambda x, y: (llx + width - x, lly + height - y)
    if rotation == 270:
        return height, width, lambda x, y: (llx + y, lly + height - x)
    raise ValueError("La rotazione PDF deve essere 0, 90, 180 o 270 gradi")


def calculate_placement(
    geometry: PageGeometry,
    *,
    page_index: int,
    preset: str,
    margin: float,
    width: float,
    height: float,
) -> SignaturePlacement:
    if preset not in PRESETS:
        raise ValueError("Preset sconosciuto")
    if margin < 0 or width <= 0 or height <= 0:
        raise ValueError("Dimensioni o margine non validi")

    display_width, display_height, transform = _display_to_page_transform(geometry)
    if width + 2 * margin > display_width or height + 2 * margin > display_height:
        raise ValueError("Il riquadro della firma non entra nella pagina")

    x1 = margin if preset.endswith("left") else display_width - margin - width
    y1 = margin if preset.startswith("bottom") else display_height - margin - height
    x2, y2 = x1 + width, y1 + height
    corners = [transform(x1, y1), transform(x1, y2), transform(x2, y1), transform(x2, y2)]
    xs = [point[0] for point in corners]
    ys = [point[1] for point in corners]
    return SignaturePlacement(page_index, min(xs), min(ys), max(xs), max(ys))

