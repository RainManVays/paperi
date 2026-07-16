from dataclasses import dataclass

import pytest

from periprint.models.enums import Orientation, PageFormat, ResidualStripPolicy
from periprint.services.grid import (
    auto_rotation_deg,
    build_grid_config,
    build_sheets,
    capacity_for,
    compact_grid_shape,
    grid_shape_for,
    orientation_of,
)


def test_orientation_of_landscape() -> None:
    assert orientation_of(200, 100) == Orientation.LANDSCAPE


def test_orientation_of_portrait() -> None:
    assert orientation_of(100, 200) == Orientation.PORTRAIT


def test_orientation_of_square() -> None:
    # Explicit branch, not a width>height bool accidentally landing on
    # PORTRAIT (docs/imposition-spec.md §6.2 / §10).
    assert orientation_of(150, 150) == Orientation.SQUARE


@pytest.mark.parametrize(
    ("cell", "content", "expected_angle"),
    [
        (Orientation.LANDSCAPE, Orientation.LANDSCAPE, 0),
        (Orientation.PORTRAIT, Orientation.PORTRAIT, 0),
        (Orientation.LANDSCAPE, Orientation.PORTRAIT, 90),
        (Orientation.PORTRAIT, Orientation.LANDSCAPE, 90),
        (Orientation.SQUARE, Orientation.PORTRAIT, 0),
        (Orientation.LANDSCAPE, Orientation.SQUARE, 0),
        (Orientation.SQUARE, Orientation.SQUARE, 0),
    ],
)
def test_auto_rotation_deg(cell: Orientation, content: Orientation, expected_angle: int) -> None:
    assert auto_rotation_deg(cell, content) == expected_angle


def test_capacity_for_known_formats() -> None:
    assert capacity_for(PageFormat.NATIVE) == 1
    assert capacity_for(PageFormat.HALF) == 2
    assert capacity_for(PageFormat.QUARTER) == 4


def test_grid_shape_for_matches_capacity() -> None:
    assert grid_shape_for(PageFormat.HALF) == (1, 2)
    assert grid_shape_for(PageFormat.QUARTER) == (2, 2)


@pytest.mark.parametrize(
    ("page_format", "count", "expected_shape"),
    [
        (PageFormat.HALF, 1, (1, 1)),
        (PageFormat.HALF, 2, (1, 2)),  # matches grid_shape_for's full grid
        (PageFormat.QUARTER, 1, (1, 1)),
        (PageFormat.QUARTER, 2, (2, 1)),  # divides the 2-wide base cols evenly -> no blank
        (PageFormat.QUARTER, 3, (2, 2)),  # "2 over 1" -> one blank cell, trailing position only
        (PageFormat.QUARTER, 4, (2, 2)),  # exact full capacity -> the real 2x2 grid
    ],
)
def test_compact_grid_shape_matches_user_confirmed_layout(
    page_format: PageFormat, count: int, expected_shape: tuple[int, int]
) -> None:
    # docs/imposition-spec.md §Б.4d: width is min(count, the format's own
    # base cols), rows follow by ceiling division — a blank cell can only
    # ever land in the trailing position of the last row (e.g. QUARTER's
    # 3-of-4 case), never a whole blank row/column, and never at all when
    # count divides the width evenly.
    cols, rows = compact_grid_shape(page_format, count)
    assert (cols, rows) == expected_shape
    assert cols * rows >= count
    assert cols * rows - count < cols  # any blank cells fit within one trailing row


def test_capacity_for_custom_is_undefined() -> None:
    # CUSTOM is outside the ISO 216 formalism on purpose (docs/imposition-
    # spec.md §0/§4) — no fixed sheet capacity, callers must route it
    # around build_sheets/build_grid_config entirely.
    with pytest.raises(ValueError):
        capacity_for(PageFormat.CUSTOM)


def test_build_grid_config_native_is_a_single_full_page_cell() -> None:
    grid = build_grid_config(PageFormat.NATIVE)

    assert len(grid.cells) == 1
    cell = grid.cells[0]
    assert (cell.x_mm, cell.y_mm, cell.width_mm, cell.height_mm) == (0.0, 0.0, 210.0, 297.0)


def test_build_grid_config_half_cells_are_always_landscape() -> None:
    # docs/imposition-spec.md §5.2 — fixed, not adapted to any content's
    # own shape (that was the old pipeline.py bug this replaces).
    grid = build_grid_config(PageFormat.HALF, ResidualStripPolicy.TRAILING)

    assert len(grid.cells) == 2
    for cell in grid.cells:
        assert orientation_of(cell.width_mm, cell.height_mm) == Orientation.LANDSCAPE
        assert (cell.width_mm, cell.height_mm) == (210.0, 148.0)
    # Stacked top-to-bottom, full sheet width each — ТЗ §5.2's own table.
    assert grid.cells[0].x_mm == grid.cells[1].x_mm == 0.0
    assert grid.cells[0].y_mm == 0.0
    assert grid.cells[1].y_mm == 148.0


def test_build_grid_config_quarter_cells_are_always_portrait_2x2() -> None:
    grid = build_grid_config(PageFormat.QUARTER, ResidualStripPolicy.TRAILING)

    assert len(grid.cells) == 4
    for cell in grid.cells:
        assert orientation_of(cell.width_mm, cell.height_mm) == Orientation.PORTRAIT
        assert (cell.width_mm, cell.height_mm) == (105.0, 148.0)
    # Reading order: (0,0), (105,0), (0,148), (105,148).
    positions = [(cell.x_mm, cell.y_mm) for cell in grid.cells]
    assert positions == [(0.0, 0.0), (105.0, 0.0), (0.0, 148.0), (105.0, 148.0)]


def test_build_grid_config_custom_has_no_fixed_grid() -> None:
    with pytest.raises(ValueError):
        build_grid_config(PageFormat.CUSTOM)


@pytest.mark.parametrize(
    ("policy", "expected_row_ys"),
    [
        (ResidualStripPolicy.TRAILING, (0.0, 148.0)),
        (ResidualStripPolicy.LEADING, (1.0, 149.0)),
        (ResidualStripPolicy.CENTERED, (0.5, 148.5)),
        (ResidualStripPolicy.DISTRIBUTED, (0.0, 149.0)),
    ],
)
def test_residual_strip_policy_only_moves_y_mm(
    policy: ResidualStripPolicy, expected_row_ys: tuple[float, float]
) -> None:
    # docs/imposition-spec.md §5.1: A5's two 148mm rows sum to 296mm, 1mm
    # short of the nominal 297mm sheet — where that 1mm goes is the only
    # thing the policy affects; cell count/width/height must stay put.
    grid = build_grid_config(PageFormat.HALF, policy)

    assert [cell.y_mm for cell in grid.cells] == list(expected_row_ys)
    assert all(cell.width_mm == 210.0 and cell.height_mm == 148.0 for cell in grid.cells)


@dataclass
class _Item:
    label: str
    fmt: PageFormat


def _labels(sheets, sheet_index: int) -> list[str]:
    return [item.label for item in sheets[sheet_index].items]


def test_build_sheets_empty_job_produces_no_sheets() -> None:
    assert build_sheets([], format_of=lambda item: item.fmt) == []


def test_build_sheets_fills_to_capacity_and_leaves_partial_last_sheet() -> None:
    # 5 QUARTER (A6, capacity 4) items -> one full sheet of 4, one partial
    # sheet of 1 (docs/imposition-spec.md §8: empty cells stay empty, no
    # stretching/recentering across the whole grid).
    items = [_Item(f"a6-{i}", PageFormat.QUARTER) for i in range(5)]

    sheets = build_sheets(items, format_of=lambda item: item.fmt)

    assert len(sheets) == 2
    assert len(sheets[0].items) == 4
    assert len(sheets[1].items) == 1
    assert sheets[0].page_format == PageFormat.QUARTER


def test_build_sheets_closes_partial_sheet_on_format_change() -> None:
    # docs/imposition-spec.md §4/§8: a format change closes even a
    # not-yet-full current sheet — no waiting for more of the same format
    # to show up later, no reordering.
    items = [
        _Item("a5-1", PageFormat.HALF),  # only 1 of 2 -> still gets closed
        _Item("a6-1", PageFormat.QUARTER),
        _Item("a6-2", PageFormat.QUARTER),
    ]

    sheets = build_sheets(items, format_of=lambda item: item.fmt)

    assert len(sheets) == 2
    assert sheets[0].page_format == PageFormat.HALF
    assert _labels(sheets, 0) == ["a5-1"]
    assert sheets[1].page_format == PageFormat.QUARTER
    assert _labels(sheets, 1) == ["a6-1", "a6-2"]


def test_build_sheets_preserves_input_order_within_a_sheet() -> None:
    items = [_Item(f"a5-{i}", PageFormat.HALF) for i in range(4)]

    sheets = build_sheets(items, format_of=lambda item: item.fmt)

    assert _labels(sheets, 0) == ["a5-0", "a5-1"]
    assert _labels(sheets, 1) == ["a5-2", "a5-3"]
