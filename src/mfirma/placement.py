from __future__ import annotations

from collections.abc import Callable

from .models import (
    DisplayRect,
    NormalizedDisplayRect,
    PageGeometry,
    SignaturePlacement,
)


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


def _page_to_display_transform(
    geometry: PageGeometry,
) -> Callable[[float, float], tuple[float, float]]:
    width, height = geometry.width, geometry.height
    llx, lly = geometry.lower_left_x, geometry.lower_left_y
    rotation = geometry.rotation % 360
    if rotation == 0:
        return lambda x, y: (x - llx, y - lly)
    if rotation == 90:
        return lambda x, y: (y - lly, width - (x - llx))
    if rotation == 180:
        return lambda x, y: (width - (x - llx), height - (y - lly))
    if rotation == 270:
        return lambda x, y: (height - (y - lly), x - llx)
    raise ValueError("La rotazione PDF deve essere 0, 90, 180 o 270 gradi")


def display_page_size(geometry: PageGeometry) -> tuple[float, float]:
    width, height, _transform = _display_to_page_transform(geometry)
    return width, height


def constrain_display_rect(
    geometry: PageGeometry,
    rect: DisplayRect,
    *,
    minimum_width: float = 1.0,
    minimum_height: float = 1.0,
) -> DisplayRect:
    display_width, display_height = display_page_size(geometry)
    width = min(max(rect.width, minimum_width), display_width)
    height = min(max(rect.height, minimum_height), display_height)
    x = min(max(rect.x, 0.0), display_width - width)
    y = min(max(rect.y, 0.0), display_height - height)
    return DisplayRect(x, y, width, height)


def display_rect_from_normalized(
    geometry: PageGeometry, rect: NormalizedDisplayRect
) -> DisplayRect:
    width, height = display_page_size(geometry)
    return DisplayRect(
        rect.x * width,
        rect.y * height,
        rect.width * width,
        rect.height * height,
    )


def normalized_from_display_rect(
    geometry: PageGeometry, rect: DisplayRect
) -> NormalizedDisplayRect:
    constrained = constrain_display_rect(geometry, rect)
    width, height = display_page_size(geometry)
    return NormalizedDisplayRect(
        constrained.x / width,
        constrained.y / height,
        constrained.width / width,
        constrained.height / height,
    )


def placement_from_display_rect(
    geometry: PageGeometry,
    *,
    page_index: int,
    rect: DisplayRect,
) -> SignaturePlacement:
    display_width, display_height, transform = _display_to_page_transform(geometry)
    constrained = constrain_display_rect(geometry, rect)
    if constrained != rect:
        raise ValueError("Il riquadro della firma non è interamente nella pagina")
    if rect.x + rect.width > display_width or rect.y + rect.height > display_height:
        raise ValueError("Il riquadro della firma non è interamente nella pagina")
    corners = (
        transform(rect.x, rect.y),
        transform(rect.x, rect.y + rect.height),
        transform(rect.x + rect.width, rect.y),
        transform(rect.x + rect.width, rect.y + rect.height),
    )
    xs = [point[0] for point in corners]
    ys = [point[1] for point in corners]
    return SignaturePlacement(page_index, min(xs), min(ys), max(xs), max(ys))


def display_rect_from_placement(
    geometry: PageGeometry, placement: SignaturePlacement
) -> DisplayRect:
    transform = _page_to_display_transform(geometry)
    corners = (
        transform(placement.x1, placement.y1),
        transform(placement.x1, placement.y2),
        transform(placement.x2, placement.y1),
        transform(placement.x2, placement.y2),
    )
    xs = [point[0] for point in corners]
    ys = [point[1] for point in corners]
    return DisplayRect(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))


def calculate_display_rect(
    geometry: PageGeometry,
    *,
    preset: str,
    margin: float,
    width: float,
    height: float,
) -> DisplayRect:
    if preset not in PRESETS:
        raise ValueError("Preset sconosciuto")
    if margin < 0 or width <= 0 or height <= 0:
        raise ValueError("Dimensioni o margine non validi")
    display_width, display_height = display_page_size(geometry)
    if width + 2 * margin > display_width or height + 2 * margin > display_height:
        raise ValueError("Il riquadro della firma non entra nella pagina")
    x = margin if preset.endswith("left") else display_width - margin - width
    y = margin if preset.startswith("bottom") else display_height - margin - height
    return DisplayRect(x, y, width, height)


def calculate_placement(
    geometry: PageGeometry,
    *,
    page_index: int,
    preset: str,
    margin: float,
    width: float,
    height: float,
) -> SignaturePlacement:
    rect = calculate_display_rect(
        geometry,
        preset=preset,
        margin=margin,
        width=width,
        height=height,
    )
    return placement_from_display_rect(
        geometry,
        page_index=page_index,
        rect=rect,
    )
