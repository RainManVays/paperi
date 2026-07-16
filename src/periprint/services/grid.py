"""Pure geometry for docs/imposition-spec.md — no PIL, no UI, no printer
hardware. Every function here is testable with plain floats/enums, which is
deliberate: the five reactive postmortems this module replaces
(_apply_page_format's HALF/QUARTER inconsistency, rotation-order bugs) were
all found live, on real images, because the geometry and the pixel-pushing
were tangled together in one function. Keeping the geometry here, and
pipeline.py responsible only for turning mm into px and pushing pixels,
means the grid math can be verified without touching PIL at all.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Generic, TypeVar

from periprint.models.enums import Orientation, PageFormat, ResidualStripPolicy

# ISO 216, rounded down to whole mm (docs/imposition-spec.md §5.1) — 148.5
# must never appear anywhere in this module or its callers.
_SHEET_WIDTH_MM = 210.0
_SHEET_HEIGHT_MM = 297.0

# Fixed cell size/orientation per content format — NOT derived from any
# content's actual proportions (docs/imposition-spec.md §5.2/§6.5: the grid
# is a static input, never adapted to what's being placed into it). HALF's
# cells are always landscape, QUARTER's always portrait — that asymmetry is
# ISO 216 itself (A6 halves A5's long side), not a bug; see the spec's own
# note on why HALF adapting its frame to content (the old pipeline.py
# behavior) violated this invariant while QUARTER never did.
_CELL_SIZE_MM: dict[PageFormat, tuple[float, float]] = {
    PageFormat.NATIVE: (210.0, 297.0),
    PageFormat.HALF: (210.0, 148.0),
    PageFormat.QUARTER: (105.0, 148.0),
}

# (cols, rows) — reading order (left-to-right, top-to-bottom) is the fill
# order, per docs/imposition-spec.md §5.4; no configurable alternative
# (open question §12.4, resolved: not requested).
_GRID_SHAPE: dict[PageFormat, tuple[int, int]] = {
    PageFormat.NATIVE: (1, 1),
    PageFormat.HALF: (1, 2),
    PageFormat.QUARTER: (2, 2),
}

_CAPACITY: dict[PageFormat, int] = {
    page_format: cols * rows for page_format, (cols, rows) in _GRID_SHAPE.items()
}


def grid_shape_for(page_format: PageFormat) -> tuple[int, int]:
    """(cols, rows) of the format's fixed *full-capacity* grid — see
    capacity_for's docstring for why CUSTOM isn't covered. This is the
    format's maximum layout, not what a partial group of fewer items
    should be packed into — see compact_grid_shape for that."""
    if page_format not in _GRID_SHAPE:
        raise ValueError(f"{page_format} has no fixed ISO 216 grid shape")
    return _GRID_SHAPE[page_format]


def compact_grid_shape(page_format: PageFormat, count: int) -> tuple[int, int]:
    """(cols, rows) to arrange exactly `count` same-sized pieces into —
    unlike grid_shape_for's fixed full-capacity shape, this is sized to
    the actual count (docs/imposition-spec.md §Б.4b/§Б.4d): PeriPrint
    prints onto a continuous roll with no physical sheet boundary forcing
    a partial group to waste a whole extra row/column blank, unlike the
    ТЗ's own sheet-fed/cut-roll model (docs/imposition-spec.md §0).

    Width is min(count, the format's own base cols) — never wider than
    the format's real grid (e.g. QUARTER never goes past 2 cols) and
    never wider than there are pieces to fill it. Rows follow from that
    by ceiling division, filled in reading order (row-major). A blank
    cell can only ever appear in the *trailing* position of the *last*
    row (e.g. 3 of QUARTER's capacity-4 grid -> 2x2 with cell 4 blank,
    confirmed against the user's own "2 over 1, not a column of three"
    correction) — never a whole blank row or column, and never for a
    count that divides the width evenly (2 of QUARTER -> 2x1, no blank
    at all)."""
    if count <= 0:
        raise ValueError("count must be positive")
    base_cols, _base_rows = _GRID_SHAPE[page_format]
    cols = min(count, base_cols)
    rows = -(-count // cols)  # ceil(count / cols) without importing math
    return (cols, rows)


def capacity_for(page_format: PageFormat) -> int:
    """Sheet capacity for a content format (docs/imposition-spec.md §4).
    CUSTOM has no ISO 216 fixed fraction of A4 (it's an arbitrary
    mm size), so it has no fixed capacity and can't go through
    build_sheets/build_grid_config — callers must route CUSTOM through
    the un-grouped single-tile-per-sheet path, same as today."""
    if page_format not in _CAPACITY:
        raise ValueError(f"{page_format} has no fixed ISO 216 sheet capacity")
    return _CAPACITY[page_format]


def orientation_of(width: float, height: float) -> Orientation:
    """Three-valued classification (docs/imposition-spec.md §6.2) — a bare
    width > height comparison silently buckets a square into PORTRAIT,
    which is a formally-right-for-the-wrong-reason result that breaks the
    moment SQUARE needs its own branch (it does, right below)."""
    if width > height:
        return Orientation.LANDSCAPE
    if width < height:
        return Orientation.PORTRAIT
    return Orientation.SQUARE


def auto_rotation_deg(cell_orientation: Orientation, content_orientation: Orientation) -> int:
    """docs/imposition-spec.md §6.2: rotate content 90° iff its orientation
    disagrees with the (fixed) cell's — SQUARE on either side means
    rotation can't meaningfully help, so it's a deliberate no-op rather
    than falling through a bool comparison by accident."""
    if Orientation.SQUARE in (cell_orientation, content_orientation):
        return 0
    return 90 if cell_orientation != content_orientation else 0


@dataclass(frozen=True)
class GridCell:
    x_mm: float
    y_mm: float
    width_mm: float
    height_mm: float
    padding_top_mm: float = 0.0
    padding_right_mm: float = 0.0
    padding_bottom_mm: float = 0.0
    padding_left_mm: float = 0.0


@dataclass(frozen=True)
class GridConfig:
    page_format: PageFormat
    cells: tuple[GridCell, ...]  # list order = fill order, see _GRID_SHAPE


def _row_offsets_mm(
    cell_height_mm: float, row_count: int, residual_mm: float, policy: ResidualStripPolicy
) -> list[float]:
    """Where each row starts along the sheet's 297mm axis, given the
    leftover from row_count * cell_height_mm falling short of 297mm
    (docs/imposition-spec.md §5.1). Only affects y_mm — never x_mm, cell
    size, or cell count (see docs/imposition-spec.md §6.5's invariant)."""
    if policy == ResidualStripPolicy.TRAILING:
        lead_mm, gap_mm = 0.0, 0.0
    elif policy == ResidualStripPolicy.LEADING:
        lead_mm, gap_mm = residual_mm, 0.0
    elif policy == ResidualStripPolicy.CENTERED:
        lead_mm, gap_mm = residual_mm / 2, 0.0
    elif policy == ResidualStripPolicy.DISTRIBUTED:
        lead_mm = 0.0
        gap_mm = residual_mm / (row_count - 1) if row_count > 1 else 0.0
    else:
        raise ValueError(f"Unknown residual_strip_policy: {policy}")

    offsets = []
    cursor = lead_mm
    for _ in range(row_count):
        offsets.append(cursor)
        cursor += cell_height_mm + gap_mm
    return offsets


def build_grid_config(
    page_format: PageFormat,
    residual_strip_policy: ResidualStripPolicy = ResidualStripPolicy.TRAILING,
) -> GridConfig:
    """Builds the static cell layout for one content format — computed
    once, never recomputed per-object (docs/imposition-spec.md §6.5: this
    is an input to the transform pipeline, not a function of what's being
    placed). Raises for CUSTOM — see capacity_for's docstring."""
    if page_format not in _CELL_SIZE_MM:
        raise ValueError(f"{page_format} has no fixed ISO 216 grid; build it explicitly")

    cell_width_mm, cell_height_mm = _CELL_SIZE_MM[page_format]
    cols, rows = _GRID_SHAPE[page_format]
    residual_mm = _SHEET_HEIGHT_MM - cell_height_mm * rows
    row_offsets = _row_offsets_mm(cell_height_mm, rows, residual_mm, residual_strip_policy)

    cells = tuple(
        GridCell(
            x_mm=col * cell_width_mm,
            y_mm=row_offsets[row],
            width_mm=cell_width_mm,
            height_mm=cell_height_mm,
        )
        for row in range(rows)
        for col in range(cols)
    )
    return GridConfig(page_format=page_format, cells=cells)


T = TypeVar("T")


@dataclass(frozen=True)
class Sheet(Generic[T]):
    page_format: PageFormat
    items: tuple[T, ...]  # may be shorter than capacity_for(page_format) — see build_sheets


def build_sheets(items: Sequence[T], format_of: Callable[[T], PageFormat]) -> list[Sheet[T]]:
    """docs/imposition-spec.md §4 — groups items into format-homogeneous
    sheets: fills a sheet to capacity_for(format), and closes the current
    (even partial) sheet the moment the format changes, rather than
    reordering to fill gaps. Input order is fill order and print order;
    this never regroups non-consecutive same-format items (open question
    §12.6 in the spec — not requested).

    Scope note (docs/imposition-spec.md §4): `items` here is whatever the
    caller has in hand — today that's one document's rendered pages, not
    the whole print queue across documents (PrintJob is 1:1 with
    DocumentItem). Nothing here assumes that boundary, so lifting it later
    is just a caller change, not a rewrite of this function.
    """
    sheets: list[Sheet[T]] = []
    current_format: PageFormat | None = None
    buffer: list[T] = []

    def _flush() -> None:
        if buffer:
            sheets.append(Sheet(page_format=current_format, items=tuple(buffer)))
            buffer.clear()

    for item in items:
        item_format = format_of(item)
        if item_format != current_format:
            _flush()
            current_format = item_format

        buffer.append(item)
        if len(buffer) == capacity_for(item_format):
            _flush()

    _flush()
    return sheets
