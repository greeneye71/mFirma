import pytest

from mfirma.models import DisplayRect, PageGeometry
from mfirma.placement import (
    calculate_display_rect,
    calculate_placement,
    constrain_display_rect,
    display_page_size,
    display_rect_from_placement,
    placement_from_display_rect,
)


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize(
    "preset", ["top_left", "top_right", "bottom_left", "bottom_right"]
)
def test_presets_stay_inside_page(rotation, preset):
    page = PageGeometry(10, 20, 605, 862, rotation)
    result = calculate_placement(
        page,
        page_index=2,
        preset=preset,
        margin=24,
        width=180,
        height=60,
    )
    assert 10 <= result.x1 < result.x2 <= 605
    assert 20 <= result.y1 < result.y2 <= 862
    assert result.page_index == 2


def test_rejects_box_that_does_not_fit():
    with pytest.raises(ValueError, match="non entra"):
        calculate_placement(
            PageGeometry(0, 0, 100, 100),
            page_index=0,
            preset="bottom_right",
            margin=10,
            width=90,
            height=20,
        )


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_custom_display_rect_roundtrips_for_all_rotations(rotation):
    geometry = PageGeometry(10, 20, 610, 820, rotation)
    rect = DisplayRect(31.5, 42.25, 190.0, 68.0)

    placement = placement_from_display_rect(
        geometry,
        page_index=3,
        rect=rect,
    )

    assert display_rect_from_placement(geometry, placement) == rect
    assert placement.page_index == 3
    expected_size = (600, 800) if rotation in (0, 180) else (800, 600)
    assert display_page_size(geometry) == expected_size


def test_display_rect_is_constrained_inside_crop_box():
    geometry = PageGeometry(0, 0, 300, 200)

    result = constrain_display_rect(
        geometry,
        DisplayRect(280, -20, 100, 90),
        minimum_width=60,
        minimum_height=30,
    )

    assert result == DisplayRect(200, 0, 100, 90)
    with pytest.raises(ValueError, match="interamente"):
        placement_from_display_rect(
            geometry,
            page_index=0,
            rect=DisplayRect(280, -20, 100, 90),
        )


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_preset_display_rect_matches_pdf_placement(rotation):
    geometry = PageGeometry(10, 20, 610, 820, rotation)
    rect = calculate_display_rect(
        geometry,
        preset="top_right",
        margin=24,
        width=190,
        height=68,
    )
    placement = calculate_placement(
        geometry,
        page_index=0,
        preset="top_right",
        margin=24,
        width=190,
        height=68,
    )

    assert display_rect_from_placement(geometry, placement) == rect
