import uuid
from pathlib import Path

import PIL.Image
import PIL.ImageDraw
import pytest

from periprint.models.document import DocumentItem, PrintSettings
from periprint.models.enums import DocumentKind, PageFormat
from periprint.services.pipeline import (
    DocumentPipeline,
    UnsupportedDocumentKindError,
    _apply_page_format,
    _compose_print_sheet,
    _pack_tiles_for_printing,
    detect_document_kind,
)


def _image_document(tmp_path: Path, width: int = 100, height: int = 200) -> DocumentItem:
    source_path = tmp_path / "source.png"
    PIL.Image.new("RGB", (width, height), color=(0, 0, 0)).save(source_path)
    return DocumentItem(id=str(uuid.uuid4()), source_path=str(source_path), kind=DocumentKind.IMAGE)


def test_render_document_applies_margins_and_chunks(tmp_path: Path) -> None:
    document = _image_document(tmp_path, width=100, height=100)
    document.settings = PrintSettings(margin_top_px=10, margin_bottom_px=20, dithering=False)

    rendered = DocumentPipeline().render_document(document, width_px=100, chunk_height_px=50)

    assert len(rendered.pages) == 1
    page = rendered.pages[0]
    # source scaled to width 100 stays 100 tall (fit_width, already correct
    # width) + 10 top margin + 20 bottom margin = 130
    assert page.image.height == 130
    assert page.image.mode == "1"
    assert sum(chunk.height for chunk in page.chunks) == 130
    assert len(page.chunks) == 3  # 50, 50, 30
    # docs/imposition-spec.md §Б.4g: real content is the 100x100 source
    # (fit to width 100), starting after the 10px top margin — the 20px
    # bottom margin is excluded, for preview_panel.py's A4 mockup.
    assert page.content_top_px == 10
    assert page.content_height_px == 100


def test_render_document_default_settings_include_bottom_margin(tmp_path: Path) -> None:
    document = _image_document(tmp_path, width=100, height=100)

    rendered = DocumentPipeline().render_document(document, width_px=100, chunk_height_px=200)

    # PrintSettings defaults to margin_bottom_px=40 (tear-off allowance),
    # margin_top_px=0 — not literally "no margins".
    assert rendered.pages[0].image.height == 140


def test_render_document_pads_to_canvas_width_without_stretching(tmp_path: Path) -> None:
    """Content must be rendered at the safe content width and padded (not
    stretched) out to the full canvas width — see printer_specs.py: feeding
    printer.printImage() anything narrower than the model's native width
    makes it stretch content into the physically-unreliable zone instead of
    leaving it blank there."""
    document = _image_document(tmp_path, width=100, height=50)
    document.settings = PrintSettings(margin_top_px=0, margin_bottom_px=0)

    rendered = DocumentPipeline().render_document(
        document, width_px=100, chunk_height_px=200, canvas_width_px=150
    )

    page = rendered.pages[0]
    assert page.image.width == 150
    assert page.image.height == 50
    # The padding (white) must be a plain right-side extension, not a
    # rescale of the original 100px-wide content.
    assert page.image.getpixel((149, 0)) != 0
    # content_width_px records the true content width *before* the
    # canvas-width padding above — used by preview_compose.py to show just
    # the meaningful piece instead of the padded, mostly-blank canvas.
    assert page.content_width_px == 100


def test_render_document_canvas_width_defaults_to_width_px(tmp_path: Path) -> None:
    document = _image_document(tmp_path, width=100, height=50)

    rendered = DocumentPipeline().render_document(document, width_px=100, chunk_height_px=200)

    assert rendered.pages[0].image.width == 100


def test_page_mode_content_length_trims_blank_pdf_tail(tmp_path: Path) -> None:
    """periprint-spec.md §3 P1: "по длине контента" should crop a mostly
    blank PDF page down to its actual content height, unlike the default
    full_page mode which keeps the entire rendered page."""
    import fitz

    pdf_path = tmp_path / "tall.pdf"
    document_handle = fitz.open()
    page = document_handle.new_page(width=200, height=1000)  # very tall, mostly blank
    page.insert_text((20, 20), "short line near the top")
    document_handle.save(str(pdf_path))
    document_handle.close()

    document = DocumentItem(id="x", source_path=str(pdf_path), kind=DocumentKind.PDF)
    document.settings = PrintSettings(page_mode="full_page", margin_top_px=0, margin_bottom_px=0)
    full_page = DocumentPipeline().render_document(document, width_px=200, chunk_height_px=5000)

    document.settings = PrintSettings(
        page_mode="content_length", margin_top_px=0, margin_bottom_px=0
    )
    trimmed = DocumentPipeline().render_document(document, width_px=200, chunk_height_px=5000)

    assert trimmed.pages[0].image.height < full_page.pages[0].image.height / 4


def test_page_range_selects_only_requested_pdf_pages(tmp_path: Path) -> None:
    import fitz

    pdf_path = tmp_path / "multi.pdf"
    document_handle = fitz.open()
    for _ in range(5):
        document_handle.new_page(width=200, height=100)
    document_handle.save(str(pdf_path))
    document_handle.close()

    document = DocumentItem(id="x", source_path=str(pdf_path), kind=DocumentKind.PDF)
    document.settings = PrintSettings(page_range="2-3,5")

    rendered = DocumentPipeline().render_document(document, width_px=200, chunk_height_px=5000)

    assert len(rendered.pages) == 3


def test_page_range_invalid_syntax_propagates(tmp_path: Path) -> None:
    import fitz

    pdf_path = tmp_path / "single.pdf"
    document_handle = fitz.open()
    document_handle.new_page(width=200, height=100)
    document_handle.save(str(pdf_path))
    document_handle.close()

    document = DocumentItem(id="x", source_path=str(pdf_path), kind=DocumentKind.PDF)
    document.settings = PrintSettings(page_range="not-a-range")

    with pytest.raises(ValueError):
        DocumentPipeline().render_document(document, width_px=200, chunk_height_px=5000)


def test_copies_repeats_rendered_pages(tmp_path: Path) -> None:
    document = _image_document(tmp_path, width=100, height=50)
    document.settings = PrintSettings(copies=3, margin_top_px=0, margin_bottom_px=0)

    rendered = DocumentPipeline().render_document(document, width_px=100, chunk_height_px=200)

    assert len(rendered.pages) == 3
    # Same processed content repeated, not re-rendered from scratch each
    # time — cheaper, and there's no reason it would differ anyway.
    assert rendered.pages[0].image is rendered.pages[1].image is rendered.pages[2].image


def test_copies_default_is_a_single_page(tmp_path: Path) -> None:
    document = _image_document(tmp_path, width=100, height=50)

    rendered = DocumentPipeline().render_document(document, width_px=100, chunk_height_px=200)

    assert len(rendered.pages) == 1


def test_page_format_half_does_not_crop_short_content(tmp_path: Path) -> None:
    """docs/stage5-ux-plan.md M5.5 postmortem #4 — the real bug: reported
    live as "он обрезан, опять" (a landscape photo got sliced in half). An
    earlier version always cropped the page into a *fixed* 2 pieces at
    full scale, discarding whatever fell outside each band — destructive
    whenever the source isn't already ~2 A5-heights tall (e.g. any single
    photo). Fixed (postmortem #5) to impose the whole page into exactly
    one A5-shaped frame via a true 2D scale-to-fit — content is shrunk to
    fit both axes at once and centered, nothing is ever lost or split."""
    document = _image_document(tmp_path, width=1000, height=200)  # landscape, like a photo
    document.settings = PrintSettings(
        page_format=PageFormat.HALF, margin_top_px=0, margin_bottom_px=0, dithering=False
    )

    rendered = DocumentPipeline().render_document(document, width_px=1664, chunk_height_px=50000)

    assert len(rendered.pages) == 1
    # HALF's cell is always the fixed 210x148mm landscape frame (@ 203dpi
    # -> 1678x1183px, width clamped to the 1664px canvas) — this landscape
    # content already matches it (auto_angle=0, no rotation needed), so
    # it's letterboxed only by the width clamp, never cropped.
    assert rendered.pages[0].image.size == (1664, 1183)
    # content_width_px equals the (clamped) frame width exactly here, since
    # it already matches the printer's full canvas width.
    assert rendered.pages[0].content_width_px == 1664


def test_page_format_quarter_does_not_crop_short_content(tmp_path: Path) -> None:
    document = _image_document(tmp_path, width=1000, height=200)
    document.settings = PrintSettings(
        page_format=PageFormat.QUARTER, margin_top_px=0, margin_bottom_px=0, dithering=False
    )

    rendered = DocumentPipeline().render_document(document, width_px=1664, chunk_height_px=50000)

    assert len(rendered.pages) == 1
    # Unlike HALF, QUARTER's frame stays the nominal portrait A6
    # (105x148mm -> 839x1183px) even for landscape content — the source
    # is rotated 90° to match instead, since QUARTER's rigid 2x2 pack
    # always needs the frame's own width doubled, and portrait keeps that
    # smaller regardless of the source's own shape (see
    # _apply_page_format's docstring). Padded out to the 1664px canvas.
    assert rendered.pages[0].image.size == (1664, 1183)


def test_page_format_half_shrinks_genuinely_tall_content_into_one_frame(tmp_path: Path) -> None:
    """postmortem #5: a source that's actually taller than one A5 frame
    (once scaled to fit) no longer paginates across multiple physical
    pieces — it shrinks further so the whole thing fits inside a *single*
    A5 frame, same as postmortem #4's short-content case. Splitting across
    pieces was itself a source of repeated bugs (postmortems #1-#3); "one
    source page = one physical frame" removes the whole class.

    docs/imposition-spec.md §5.2/§6.2 update: the frame itself is fixed
    (always the landscape 210x148mm HALF cell) regardless of content shape
    — this very tall, portrait-shaped source gets auto-rotated to match
    the cell first, then fit into exactly the same frame size as the
    short-content case above, not a taller portrait one."""
    document = _image_document(tmp_path, width=1000, height=3000)  # tall, portrait
    document.settings = PrintSettings(
        page_format=PageFormat.HALF, margin_top_px=0, margin_bottom_px=0, dithering=False
    )

    rendered = DocumentPipeline().render_document(document, width_px=1664, chunk_height_px=50000)

    assert len(rendered.pages) == 1
    assert rendered.pages[0].image.size == (1664, 1183)


def test_page_format_half_target_width_clamped_to_printer_width(tmp_path: Path) -> None:
    """A5's fixed cell width (210mm ~= 1678px at 203dpi) can exceed a
    narrow-roll printer model's own safe content width (e.g. ~384px for
    the A6 hardware line) — clamp to whatever the active printer can
    actually do rather than asking _pad_to_canvas_width to shrink
    something it only ever widens. Frame height has no such clamp (it
    runs along the continuous roll, not across the fixed print width).
    Source here is portrait, so it's auto-rotated to match the fixed
    landscape cell before this clamp is even applied."""
    document = _image_document(tmp_path, width=200, height=280)
    document.settings = PrintSettings(
        page_format=PageFormat.HALF, margin_top_px=0, margin_bottom_px=0, dithering=False
    )

    rendered = DocumentPipeline().render_document(document, width_px=384, chunk_height_px=50000)

    assert rendered.pages[0].image.size == (384, 1183)


def test_page_format_half_cell_size_is_fixed_regardless_of_rotation_or_shape() -> None:
    """docs/imposition-spec.md §5.2/§6.5 — the core invariant this rewrite
    exists for: HALF's cell is always the same 210x148mm landscape frame,
    never adapted to content orientation or rotation (the old code
    reshaped the *frame* for HALF specifically, which broke the
    single-rule-for-every-format promise QUARTER already followed).
    fit_into_frame() always outputs exactly the frame's own pixel size
    regardless of input shape, so this holds for every combination."""
    shapes = [
        PIL.Image.new("L", (1000, 600), color=0),  # landscape
        PIL.Image.new("L", (600, 1000), color=0),  # portrait
        PIL.Image.new("L", (800, 800), color=0),  # square
    ]

    for source in shapes:
        for rotation_degrees in (0, 90, 180, 270):
            settings = PrintSettings(page_format=PageFormat.HALF, rotation_degrees=rotation_degrees)
            tiles = _apply_page_format(source, settings, width_px=5000)
            assert tiles[0].size == (1678, 1183)


def test_page_format_half_auto_rotates_portrait_content_to_fill_the_landscape_cell() -> None:
    """docs/imposition-spec.md §6.2 — content whose native shape is
    exactly A5 (148x210mm) but authored portrait gets auto-rotated 90° to
    match HALF's fixed landscape cell, filling it edge to edge with zero
    letterbox — the mirror image of the old (removed) behavior where the
    *frame* swapped to portrait instead of rotating the content."""
    source = PIL.Image.new("L", (148, 210), color=0)  # exactly A5, portrait
    settings = PrintSettings(page_format=PageFormat.HALF)

    tiles = _apply_page_format(source, settings, width_px=5000)

    assert tiles[0].size == (1678, 1183)
    assert tiles[0].getpixel((0, 0)) == 0
    assert tiles[0].getpixel((1677, 1182)) == 0


def test_page_format_half_landscape_content_needs_no_auto_rotation() -> None:
    source = PIL.Image.new("L", (210, 148), color=0)  # already A5-landscape

    tiles = _apply_page_format(source, PrintSettings(page_format=PageFormat.HALF), width_px=5000)

    assert tiles[0].size == (1678, 1183)
    assert tiles[0].getpixel((0, 0)) == 0
    assert tiles[0].getpixel((1677, 1182)) == 0


def test_page_format_half_manual_rotation_can_fight_auto_rotation_and_letterbox() -> None:
    """docs/imposition-spec.md §6.1/§6.3/§8: manual rotation is added *on
    top* of auto-rotation and is explicitly allowed to undo its alignment
    — previously impossible for HALF, since the old adaptive-frame code
    always avoided rotating content by reshaping the frame instead.
    A source exactly A5-shaped but portrait gets auto_angle=90 (lining it
    up with the landscape cell, per the test above); an *additional*
    manual 90° cancels that back out, so total_angle=180 leaves it
    portrait-shaped inside the landscape frame -> letterboxed left/right,
    not an error (spec §8)."""
    source = PIL.Image.new("L", (148, 210), color=0)
    settings = PrintSettings(page_format=PageFormat.HALF, rotation_degrees=90)

    tiles = _apply_page_format(source, settings, width_px=5000)

    assert tiles[0].size == (1678, 1183)
    assert tiles[0].getpixel((0, 591)) == 255  # left letterbox
    assert tiles[0].getpixel((1677, 591)) == 255  # right letterbox
    assert tiles[0].getpixel((839, 591)) == 0  # actual content, centered


def test_page_format_half_square_content_gets_zero_auto_rotation() -> None:
    """SQUARE content routes through auto_rotation_deg's explicit
    SQUARE branch (auto_angle=0, see test_grid.py for the branch itself)
    rather than an accidental bool-comparison fallthrough — the pipeline
    integration just needs to not crash and keep the cell's fixed size,
    the branch logic itself is unit-tested directly in services/grid.py."""
    source = PIL.Image.new("L", (1000, 1000), color=0)

    tiles = _apply_page_format(source, PrintSettings(page_format=PageFormat.HALF), width_px=5000)

    assert tiles[0].size == (1678, 1183)


def test_page_format_quarter_rotates_landscape_content_to_fit_portrait_frame() -> None:
    """The mirror image of HALF's rule: QUARTER's frame stays the nominal
    portrait A6 (105x148mm) regardless of the source's own shape, and a
    landscape source is rotated 90° to match it instead of the frame
    swapping to landscape. Why: QUARTER's pack is always a rigid 2x2 grid
    (_grid_shape_for), so the frame's own width is always doubled for
    packing either way — landscape (148mm) would need 2x the packing
    width of portrait (105mm) for the exact same 4-up layout, for no
    benefit, unlike HALF where either orientation costs the same."""
    source = PIL.Image.new("L", (1000, 600), color=0)  # landscape
    settings = PrintSettings(page_format=PageFormat.QUARTER, rotation_degrees=0)

    tiles = _apply_page_format(source, settings, width_px=5000)

    assert len(tiles) == 1
    # A6's nominal (105, 148)mm @ 203dpi -> 839x1183px, unswapped.
    assert tiles[0].size == (839, 1183)


def test_rotation_alone_rotates_the_whole_page_without_splitting(tmp_path: Path) -> None:
    document = _image_document(tmp_path, width=100, height=50)
    document.settings = PrintSettings(
        rotation_degrees=90, margin_top_px=0, margin_bottom_px=0, dithering=False
    )

    rendered = DocumentPipeline().render_document(document, width_px=100, chunk_height_px=5000)

    assert len(rendered.pages) == 1
    # 100x50 rotated 90 -> 50x100, re-fit to width_px=100 doubles both axes.
    assert rendered.pages[0].image.width == 100
    assert rendered.pages[0].image.height == 200


def test_mirror_horizontal_applies_before_rotation() -> None:
    """docs/imposition-spec.md §6 — mirror is step 1, before any rotation
    (auto or manual): a top-left marker mirrored horizontally moves to the
    top-right *first*, then the 90° rotation carries it from there — a
    different final position than rotating first and mirroring second
    would produce, since the two operations don't commute."""
    source = PIL.Image.new("L", (4, 2), color=255)
    source.putpixel((0, 0), 0)
    settings = PrintSettings(mirror_horizontal=True, rotation_degrees=90)

    tiles = _apply_page_format(source, settings, width_px=2)

    assert tiles[0].size == (2, 4)
    assert tiles[0].getpixel((0, 0)) == 0


def test_mirror_flag_also_applies_to_half_format() -> None:
    """Mirror is a general first step (docs/imposition-spec.md §6), not
    NATIVE-specific — it must still run when page_format routes content
    through the fixed-grid HALF path instead of the plain fit_to_width
    one."""
    source = PIL.Image.new("L", (210, 148), color=255)  # exact A5 landscape, zero letterbox
    PIL.ImageDraw.Draw(source).rectangle([0, 0, 40, 20], fill=0)  # asymmetric marker
    plain_settings = PrintSettings(page_format=PageFormat.HALF)
    mirrored_settings = PrintSettings(page_format=PageFormat.HALF, mirror_horizontal=True)

    plain_tiles = _apply_page_format(source, plain_settings, width_px=5000)
    mirrored_tiles = _apply_page_format(source, mirrored_settings, width_px=5000)

    assert list(plain_tiles[0].getdata()) != list(mirrored_tiles[0].getdata())


def test_page_format_custom_fits_content_into_single_explicit_mm_frame(tmp_path: Path) -> None:
    document = _image_document(tmp_path, width=100, height=1000)
    document.settings = PrintSettings(
        page_format=PageFormat.CUSTOM,
        custom_tile_width_mm=25.4,  # -> 203px at PRINT_DPI=203
        custom_tile_height_mm=25.4,
        margin_top_px=0,
        margin_bottom_px=0,
        dithering=False,
    )

    # width_px=300 is wide enough that the custom 203x203px target isn't
    # clamped (see the dedicated clamp test below) — a very tall 100x1000
    # source scaled to fit a 203x203 frame is height-bound
    # (scale = 203/1000 = 0.203), landing as one letterboxed frame, not
    # split across multiple pieces.
    rendered = DocumentPipeline().render_document(document, width_px=300, chunk_height_px=5000)

    assert len(rendered.pages) == 1
    # 203x203 frame widened (never shrunk) to the 300px canvas by
    # _pad_to_canvas_width; height is untouched since that only pads width.
    assert rendered.pages[0].image.size == (300, 203)


def test_page_format_custom_target_width_clamped_to_printer_width(tmp_path: Path) -> None:
    document = _image_document(tmp_path, width=100, height=1000)
    document.settings = PrintSettings(
        page_format=PageFormat.CUSTOM,
        custom_tile_width_mm=25.4,  # -> 203px, wider than width_px below
        custom_tile_height_mm=25.4,
        margin_top_px=0,
        margin_bottom_px=0,
        dithering=False,
    )

    rendered = DocumentPipeline().render_document(document, width_px=100, chunk_height_px=5000)

    assert rendered.pages[0].image.size == (100, 203)


def test_pack_tiles_for_printing_packs_two_half_pieces_stacked() -> None:
    """The point of the whole feature: printing must match what the
    preview's A4 mockup shows — 2 A5 pieces must print as ONE pass, not
    two. HALF pieces are always the fixed landscape cell shape (see
    _place_content_in_cell/services/grid.py), stacked vertically per
    docs/imposition-spec.md §5.2's own "сверху вниз" table — not packed
    side by side based on the piece's own shape, unlike before this
    rewrite."""
    piece = PIL.Image.new("L", (1678, 1183), color=0)  # A5 cell, always landscape

    packed = _pack_tiles_for_printing([piece, piece], PageFormat.HALF, width_px=5000)

    assert len(packed) == 1
    assert packed[0].size == (1678, 1183 * 2)


def test_pack_tiles_for_printing_shrinks_slightly_to_close_a_near_miss() -> None:
    """Real-world case that motivated _MAX_PACK_SHRINK: on the A40 (safe
    content width 1664px), 2 portrait A6s side by side need 839*2=1678px —
    14px over, purely from mm-to-px rounding, not because A6 genuinely
    doesn't fit two-up on that hardware. Refusing to pack over 14px would
    make the whole feature never fire on real A6-format/A40 hardware."""
    piece = PIL.Image.new("L", (839, 1183), color=0)

    packed = _pack_tiles_for_printing([piece] * 4, PageFormat.QUARTER, width_px=1664)

    assert len(packed) == 1
    # scale = 1664/1678 ~= 0.9917 -> each piece shrinks from 839x1183 to
    # 832x1173 (rounded), so 2x2 of them exactly fill the 1664px width.
    assert packed[0].size == (1664, 1173 * 2)


def test_pack_tiles_for_printing_always_packs_shrinking_as_much_as_needed() -> None:
    """No refuse-to-pack cutoff: HALF always packs its 2 pieces, shrinking
    them as far as needed to fit width_px — the same "clamp to whatever
    the printer can do" precedent _place_content_in_cell already applies
    to a single un-packed piece (down to 384px for the "A6" hardware
    line's own A5 output, a much bigger cut than this one). 1678px (A5's
    real cell width) needs a shrink to fit a 1664px printer — it still
    packs."""
    piece = PIL.Image.new("L", (1678, 1183), color=0)

    packed = _pack_tiles_for_printing([piece, piece], PageFormat.HALF, width_px=1664)

    assert len(packed) == 1
    assert packed[0].size == (1664, 1173 * 2)


def test_pack_tiles_for_printing_leaves_lone_trailing_piece_unpacked() -> None:
    # 3 copies of a capacity-2 format: the first 2 pack together (stacked,
    # docs/imposition-spec.md §5.2), the 3rd has nothing left to pair with
    # — compact_grid_shape(HALF, 1) == (1, 1), a no-op "pack" that leaves
    # it exactly as it was, same as before this rewrite for the lone case.
    piece = PIL.Image.new("L", (1678, 1183), color=0)

    packed = _pack_tiles_for_printing([piece, piece, piece], PageFormat.HALF, width_px=5000)

    assert len(packed) == 2
    assert packed[0].size == (1678, 1183 * 2)
    assert packed[1].size == (1678, 1183)


def test_pack_tiles_for_printing_quarter_packs_four_into_2x2_grid() -> None:
    piece = PIL.Image.new("L", (839, 1183), color=0)  # portrait A6-shaped

    packed = _pack_tiles_for_printing([piece] * 4, PageFormat.QUARTER, width_px=5000)

    assert len(packed) == 1
    assert packed[0].size == (839 * 2, 1183 * 2)


def test_pack_tiles_for_printing_quarter_packs_a_partial_group_compactly() -> None:
    """The exact bug the user hit live: 2 copies of QUARTER (A6, capacity
    4) used to fall back to 2 separate un-packed pages (only an *exact*
    full group of 4 ever packed), while 4 copies packed into one page —
    inconsistent depending on whether the count divided capacity evenly.
    docs/imposition-spec.md §Б.4d: 2 divides QUARTER's base 2 cols evenly
    -> packs side by side (2x1), zero blank cells."""
    piece = PIL.Image.new("L", (839, 1183), color=0)

    packed = _pack_tiles_for_printing([piece, piece], PageFormat.QUARTER, width_px=5000)

    assert len(packed) == 1
    assert packed[0].size == (839 * 2, 1183)


def test_pack_tiles_for_printing_quarter_packs_three_as_two_over_one() -> None:
    # docs/imposition-spec.md §Б.4d (user-confirmed layout): 3 of
    # QUARTER's capacity-4 grid packs as "2 over 1" — a 2x2 canvas with
    # the trailing (bottom-right) cell blank — not a column of three
    # separate single-wide rows.
    piece = PIL.Image.new("L", (839, 1183), color=0)

    packed = _pack_tiles_for_printing([piece, piece, piece], PageFormat.QUARTER, width_px=5000)

    assert len(packed) == 1
    assert packed[0].size == (839 * 2, 1183 * 2)
    # Bottom-right cell (the 4th slot, never pasted) stays blank/white.
    assert packed[0].getpixel((839 + 10, 1183 + 10)) == 255


def test_pack_tiles_for_printing_native_format_never_packs() -> None:
    # NATIVE/CUSTOM have no fixed ISO-216 relationship to A4, so there's
    # no "N per sheet" to pack toward — always returned unpacked.
    piece = PIL.Image.new("L", (1000, 1000), color=0)
    tiles = [piece, piece]

    packed = _pack_tiles_for_printing(tiles, PageFormat.NATIVE, width_px=5000)

    assert packed == tiles


def test_compose_print_sheet_draws_a_cut_guide_between_pieces() -> None:
    piece = PIL.Image.new("L", (1183, 1678), color=0)

    sheet = _compose_print_sheet([piece, piece], cols=2, rows=1)

    assert sheet.size == (1183 * 2, 1678)
    # Somewhere in the first dash segment (the cut guide always starts
    # right at the top) there must be a black pixel on the seam column.
    assert any(sheet.getpixel((1183, y)) == 0 for y in range(20))


def test_render_document_packs_copies_into_one_physical_print_pass(tmp_path: Path) -> None:
    """End-to-end: 2 copies of a portrait source in A5 format, wide enough
    printer — must render as ONE physical page, not two, so
    PrintJobManager actually prints them side by side instead of
    sequentially with a feed gap between.

    docs/imposition-spec.md §5.2: HALF's cell is now always the fixed
    landscape 210x148mm frame, so _grid_shape_for stacks the 2 pieces
    vertically (1 col x 2 rows) — the exact "сверху вниз" arrangement of
    ТЗ §5.2's own table, not a content-dependent side-by-side pack. The
    composed sheet's *width* is therefore one piece's width (1678px), not
    two side-by-side pieces' combined width."""
    document = _image_document(tmp_path, width=200, height=280)  # portrait
    document.settings = PrintSettings(
        page_format=PageFormat.HALF,
        copies=2,
        margin_top_px=0,
        margin_bottom_px=0,
        dithering=False,
    )

    rendered = DocumentPipeline().render_document(document, width_px=5000, chunk_height_px=50000)

    assert len(rendered.pages) == 1
    assert rendered.pages[0].content_width_px == 1678
    assert rendered.pages[0].image.width == 5000


def test_render_document_packs_even_on_a_narrow_printer_by_shrinking(tmp_path: Path) -> None:
    # Same as above but width_px=1664 — 2*1183=2366 doesn't fit at nominal
    # A5 size, but copies still pack into one physical page, shrunk to
    # whatever the printer can do, same as a single un-packed piece would
    # be (there's no refuse-to-pack cutoff).
    document = _image_document(tmp_path, width=200, height=280)
    document.settings = PrintSettings(
        page_format=PageFormat.HALF,
        copies=2,
        margin_top_px=0,
        margin_bottom_px=0,
        dithering=False,
    )

    rendered = DocumentPipeline().render_document(document, width_px=1664, chunk_height_px=50000)

    assert len(rendered.pages) == 1
    assert rendered.pages[0].content_width_px == 1664


def test_render_document_packs_partial_quarter_copies_onto_one_page(tmp_path: Path) -> None:
    """The exact bug reported live: 2 copies of QUARTER (A6) used to
    render as 2 separate pages (only an exact multiple of capacity_for
    ever packed), while 4 copies rendered as 1 — inconsistent purely
    because 2 doesn't divide QUARTER's capacity of 4 evenly.
    docs/imposition-spec.md §Б.4d: any count from 1 up now packs onto one
    page, sized to the actual count (2 divides QUARTER's 2 base cols
    evenly, so this packs side by side, same width as the full 4-copy
    grid)."""
    document = _image_document(tmp_path, width=200, height=280)
    document.settings = PrintSettings(
        page_format=PageFormat.QUARTER,
        copies=2,
        margin_top_px=0,
        margin_bottom_px=0,
        dithering=False,
    )

    rendered = DocumentPipeline().render_document(document, width_px=5000, chunk_height_px=50000)

    assert len(rendered.pages) == 1
    assert rendered.pages[0].content_width_px == 839 * 2


def test_render_document_packs_against_native_width_not_the_unconfirmed_safe_width(
    tmp_path: Path,
) -> None:
    """The packing budget is target_canvas_width (the printer's real
    native row width, e.g. 1728 for A40 — verified in Stage 0 against
    actual hardware), not width_px (safe_content_width_px, an unconfirmed
    single-byte guess per printer_specs.py's own TODO). 4 portrait A6
    copies need 839*2=1678px, which fits the native 1728px width with
    room to spare even though it narrowly misses the "safe" 1664px one."""
    document = _image_document(tmp_path, width=200, height=280)  # portrait
    document.settings = PrintSettings(
        page_format=PageFormat.QUARTER,
        copies=4,
        margin_top_px=0,
        margin_bottom_px=0,
        dithering=False,
    )

    rendered = DocumentPipeline().render_document(
        document, width_px=1664, chunk_height_px=50000, canvas_width_px=1728
    )

    assert len(rendered.pages) == 1
    # 1678 < 1728, so no shrink was even needed to fit — full nominal A6
    # size (839x1183 each) in a 2x2 grid.
    assert rendered.pages[0].content_width_px == 839 * 2


def test_render_document_packs_landscape_quarter_copies_by_rotating_content(
    tmp_path: Path,
) -> None:
    """The real bug report this fixed: a landscape photo (e.g. a
    motorcycle) in QUARTER format used to get a landscape-swapped A6
    frame (148mm wide) — 4 copies of *that* need 2*1183=2366px, missing
    even the native 1728px width, so packing fell back to 4 separate
    pages. Rotating the content into the frame instead of swapping the
    frame keeps the packing width at 839px, well within budget — no
    shrink needed at all, same as the portrait-source case above."""
    document = _image_document(tmp_path, width=280, height=200)  # landscape
    document.settings = PrintSettings(
        page_format=PageFormat.QUARTER,
        copies=4,
        margin_top_px=0,
        margin_bottom_px=0,
        dithering=False,
    )

    rendered = DocumentPipeline().render_document(
        document, width_px=1664, chunk_height_px=50000, canvas_width_px=1728
    )

    assert len(rendered.pages) == 1
    assert rendered.pages[0].content_width_px == 839 * 2


def test_native_format_rotation_preserves_actual_size_fit_mode() -> None:
    """fit_mode and rotation are independent UI controls (preview_panel.py)
    — a user can pick "как есть" (actual_size) together with a 90°/270°
    rotation. _apply_page_format used to hardcode "fit_width" after
    rotating, silently discarding actual_size/crop whenever rotation
    swapped width and height. Now it passes settings.fit_mode through.
    Exercised directly against _apply_page_format (rather than through
    render_document) so the renderer's own separate width_px pre-fit pass
    doesn't confound what's being checked here."""
    source = PIL.Image.new("L", (50, 30), color=0)
    settings = PrintSettings(fit_mode="actual_size", rotation_degrees=90)

    tiles = _apply_page_format(source, settings, width_px=100)

    assert len(tiles) == 1
    # 50x30 rotated 90 -> 30x50; actual_size must center it on a 100-wide
    # white canvas at native scale (height stays 50), not rescale it to
    # fill the width (which "fit_width" would do, changing the height too).
    assert tiles[0].size == (100, 50)


def test_unsupported_kind_raises(tmp_path: Path) -> None:
    source_path = tmp_path / "note.md"
    source_path.write_text("# heading", encoding="utf-8")
    document = DocumentItem(id="x", source_path=str(source_path), kind=DocumentKind.MARKDOWN)

    with pytest.raises(UnsupportedDocumentKindError):
        DocumentPipeline().render_document(document, width_px=384, chunk_height_px=220)


@pytest.mark.parametrize(
    ("filename", "expected_kind"),
    [
        ("photo.png", DocumentKind.IMAGE),
        ("photo.JPG", DocumentKind.IMAGE),
        ("scan.jpeg", DocumentKind.IMAGE),
        ("icon.bmp", DocumentKind.IMAGE),
        ("notes.txt", DocumentKind.TEXT),
        ("report.pdf", DocumentKind.PDF),
        ("readme.md", DocumentKind.MARKDOWN),
    ],
)
def test_detect_document_kind(filename: str, expected_kind: DocumentKind) -> None:
    assert detect_document_kind(f"/some/path/{filename}") == expected_kind


def test_detect_document_kind_unknown_extension() -> None:
    assert detect_document_kind("/some/path/file.xyz") is None
