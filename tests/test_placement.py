import pytest

from mfirma.models import PageGeometry
from mfirma.placement import calculate_placement


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

