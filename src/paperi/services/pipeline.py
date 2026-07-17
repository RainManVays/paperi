from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF
import PIL.Image
import PIL.ImageDraw

from paperi.infra.renderers.base import (
    Renderer,
    apply_mirror,
    fit_into_frame,
    fit_to_width,
    normalize_to_1bit,
    rotate_page,
    slice_into_chunks,
    trim_to_content_height,
)
from paperi.infra.renderers.image_renderer import ImageRenderer
from paperi.infra.renderers.pdf_renderer import PdfRenderer
from paperi.infra.renderers.text_renderer import TextRenderer
from paperi.models.document import DocumentItem, PrintSettings
from paperi.models.enums import DocumentKind, PageFormat
from paperi.models.printer_specs import mm_to_px
from paperi.services.grid import (
    auto_rotation_deg,
    build_grid_config,
    build_sheets,
    compact_grid_shape,
    orientation_of,
)
from paperi.utils.page_range import parse_page_range

_RENDERERS: dict[DocumentKind, Renderer] = {
    DocumentKind.IMAGE: ImageRenderer(),
    DocumentKind.PDF: PdfRenderer(),
    DocumentKind.TEXT: TextRenderer(),
}

_EXTENSION_TO_KIND: dict[str, DocumentKind] = {
    ".png": DocumentKind.IMAGE,
    ".jpg": DocumentKind.IMAGE,
    ".jpeg": DocumentKind.IMAGE,
    ".bmp": DocumentKind.IMAGE,
    ".txt": DocumentKind.TEXT,
    ".pdf": DocumentKind.PDF,
    ".md": DocumentKind.MARKDOWN,
}

# Only extensions whose kind has an actual registered renderer — .md maps
# to a real DocumentKind but MarkdownRenderer doesn't exist yet (Stage 6/
# P1), so detect_document_kind() accepts it while rendering always fails
# later. Used to tell the user what genuinely works right now (dropzone
# caption, docs/stage5-ux-plan.md's post-launch UX fixes) rather than
# silently including a format that's guaranteed to error out.
SUPPORTED_EXTENSIONS: tuple[str, ...] = tuple(
    sorted(ext for ext, kind in _EXTENSION_TO_KIND.items() if kind in _RENDERERS)
)


class UnsupportedDocumentKindError(Exception):
    pass


def detect_document_kind(source_path: str) -> DocumentKind | None:
    return _EXTENSION_TO_KIND.get(Path(source_path).suffix.lower())


@dataclass
class RenderedPage:
    image: PIL.Image.Image  # normalized 1-bit, full canvas width — for preview
    chunks: list[PIL.Image.Image]  # same image sliced by chunk_height_px
    # Width of the actual imposed content before _pad_to_canvas_width
    # widened it out to the printer's full canvas width — i.e. the true
    # A5/A6/CUSTOM frame width (or fit_mode's own width for NATIVE). Lets
    # UI code (preview_panel.py's A4 mockup) show just the meaningful
    # piece instead of the mostly-blank full-canvas-width image.
    content_width_px: int
    # y-offset and height of the real imposed content within `image`,
    # before _apply_margins added margin_top_px/margin_bottom_px (the
    # tear-off feed allowance) above/below it. docs/imposition-spec.md
    # §Б.4g: without this, preview_panel.py's A4 mockup compared the
    # margin-inclusive image against a nominal A4 sheet, so the tear-off
    # margin (not real content) visibly poked out past the drawn A4
    # outline by a few mm — informative for neither "does the grid fit on
    # A4" nor "here's the tear-off allowance", just confusing. Mirrors
    # content_width_px's own purpose, extended to the height axis.
    content_top_px: int
    content_height_px: int


@dataclass
class RenderedDocument:
    # One RenderedPage per PDF page (or a single page for image/text
    # documents) — kept as an explicit boundary, not flattened into one
    # continuous raster, so a multi-page PDF prints "постранично" (spec
    # §3): PrintJobManager (Stage 4) can insert a break between pages
    # distinct from the inter-chunk cooldown pause within a page.
    pages: list[RenderedPage]


def _apply_margins(image: PIL.Image.Image, settings: PrintSettings) -> PIL.Image.Image:
    if settings.margin_top_px == 0 and settings.margin_bottom_px == 0:
        return image
    new_height = image.height + settings.margin_top_px + settings.margin_bottom_px
    canvas = PIL.Image.new(image.mode, (image.width, new_height), color=255)
    canvas.paste(image, (0, settings.margin_top_px))
    return canvas


def _count_pages(document: DocumentItem) -> int:
    """Cheap page count for parsing page_range against — just opens the
    PDF's structure, doesn't rasterize anything. Non-PDF documents are
    always exactly 1 "page"."""
    if document.kind != DocumentKind.PDF:
        return 1
    with fitz.open(document.source_path) as pdf:
        return len(pdf)


def _place_in_custom_frame(
    image: PIL.Image.Image, settings: PrintSettings, width_px: int
) -> PIL.Image.Image:
    """CUSTOM tile sizes aren't an ISO 216 fraction of A4 (docs/imposition-
    spec.md §0/§11 — out of the ТЗ's formal scope), so they stay outside
    the fixed-grid formalism build_grid_config implements for HALF/
    QUARTER: the frame's own orientation still adapts to the (rotated)
    content's shape to minimize letterbox, same behavior as before this
    rewrite — there's no spec-mandated "correct" fixed orientation for an
    arbitrary user-chosen size to justify changing it."""
    page = rotate_page(image, settings.rotation_degrees)
    target_width_mm = settings.custom_tile_width_mm
    target_height_mm = settings.custom_tile_height_mm
    if page.width > page.height:
        target_width_mm, target_height_mm = (
            max(target_width_mm, target_height_mm),
            min(target_width_mm, target_height_mm),
        )
    else:
        target_width_mm, target_height_mm = (
            min(target_width_mm, target_height_mm),
            max(target_width_mm, target_height_mm),
        )
    # Frame width clamped to width_px — see _place_content_in_cell's own
    # comment on why (narrower physical rolls can't fit the nominal size).
    frame_width_px = min(mm_to_px(target_width_mm), width_px)
    frame_height_px = mm_to_px(target_height_mm)
    return fit_into_frame(page, frame_width_px, frame_height_px)


def _place_content_in_cell(
    image: PIL.Image.Image, settings: PrintSettings, width_px: int
) -> PIL.Image.Image:
    """docs/imposition-spec.md §6.3 — the one rule shared by HALF and
    QUARTER, replacing what used to be two different, inconsistent ones:
    HALF used to reshape its *frame* to match the content's own
    orientation (avoiding rotation, but making the grid a function of
    content — a direct violation of §6.5's "grid is a static input"
    invariant), while QUARTER rotated *content* to match a frame that
    never moved. Now both go through the same fixed GridConfig
    (services/grid.py) and the same auto-rotate rule: content bends to
    the grid, never the other way around, for every format.

    Auto-rotation compares the cell's *fixed* orientation against the
    content's *native* (pre-rotation) shape; settings.rotation_degrees is
    added on top of that result and is allowed to fight it, producing
    letterboxing rather than an error (spec §6.1/§8/§10) — a case the old
    QUARTER path silently "corrected" away by re-deriving its rotation
    from the already-manually-rotated page, and the old HALF path could
    never produce at all.

    All cells of a given format share one size (only x/y differ across
    cells — see grid.py's _CELL_SIZE_MM), so cells[0] is representative
    for sizing here; which physical cell of the eventual composed sheet
    each tile lands in is still decided later by _pack_tiles_for_printing,
    unchanged by this function.
    """
    grid = build_grid_config(settings.page_format)
    cell = grid.cells[0]

    cell_orientation = orientation_of(cell.width_mm, cell.height_mm)
    content_orientation = orientation_of(image.width, image.height)
    auto_angle = auto_rotation_deg(cell_orientation, content_orientation)
    total_angle = (auto_angle + settings.rotation_degrees) % 360
    rotated = rotate_page(image, total_angle)

    inner_width_mm = cell.width_mm - cell.padding_left_mm - cell.padding_right_mm
    inner_height_mm = cell.height_mm - cell.padding_top_mm - cell.padding_bottom_mm
    # Frame width clamped to width_px: cell sizes are fixed real-world mm
    # (210x148 for A5, 105x148 for A6) independent of which printer model
    # is active — on a narrow-roll model (e.g. the A6 line, ~48mm real
    # width) the requested size may simply not be physically achievable.
    # Scaling down further to whatever the active printer *can* do is the
    # safe fallback; _pad_to_canvas_width later on only ever widens, never
    # shrinks, so this has to be enforced here. Frame height has no such
    # clamp — it runs along the continuous roll, not across its fixed
    # width.
    frame_width_px = min(mm_to_px(inner_width_mm), width_px)
    frame_height_px = mm_to_px(inner_height_mm)
    return fit_into_frame(rotated, frame_width_px, frame_height_px)


def _apply_page_format(
    raw_page: PIL.Image.Image, settings: PrintSettings, width_px: int
) -> list[PIL.Image.Image]:
    """docs/imposition-spec.md §6 — fixed transform order for every
    format: mirror (bbox-preserving, applied to native content) -> per-
    format placement, which itself applies auto-rotation before
    settings.rotation_degrees, then fits into the target frame without
    cropping. A multi-page PDF already supplies one raw_page per PDF
    page, so a document authored as N A5-sized pages naturally becomes N
    A5 frames with no extra pagination logic needed here.

    NATIVE: no imposition — page just rotates and fills the canvas per
    settings.fit_mode (the standalone "rotate my sideways photo" case,
    predating imposition entirely; not part of the ТЗ's grid formalism —
    see docs/imposition-spec.md §0)."""
    image = apply_mirror(raw_page, settings.mirror_horizontal, settings.mirror_vertical)

    if settings.page_format == PageFormat.NATIVE:
        rotated = rotate_page(image, settings.rotation_degrees)
        return [fit_to_width(rotated, width_px, settings.fit_mode)]

    if settings.page_format == PageFormat.CUSTOM:
        return [_place_in_custom_frame(image, settings, width_px)]

    return [_place_content_in_cell(image, settings, width_px)]


def _draw_dashed_line(
    draw: PIL.ImageDraw.ImageDraw,
    xy: tuple[tuple[int, int], tuple[int, int]],
    dash: int = 20,
    gap: int = 12,
) -> None:
    """Cut guide, not a solid line — reads as "cut here" on the printed
    thermal paper rather than looking like a stray printed bar or defect."""
    (x0, y0), (x1, y1) = xy
    length = round(((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5)
    if length == 0:
        return
    step_x, step_y = (x1 - x0) / length, (y1 - y0) / length
    position = 0
    while position < length:
        seg_end = min(position + dash, length)
        draw.line(
            [
                (round(x0 + step_x * position), round(y0 + step_y * position)),
                (round(x0 + step_x * seg_end), round(y0 + step_y * seg_end)),
            ],
            fill=0,
            width=2,
        )
        position += dash + gap


def _compose_print_sheet(
    pieces: list[PIL.Image.Image], cols: int, rows: int, scale: float = 1.0
) -> PIL.Image.Image:
    """Packs same-size `pieces` (all sharing one page_format/rotation, so
    one uniform size) into a single cols x rows grid, edge to edge, with a
    dashed cut guide between neighbors — the actual pixels that get
    printed, not just a preview mockup. Always called with exactly
    cols*rows pieces (see _pack_tiles_for_printing/compact_grid_shape) —
    the shape itself is chosen to fit however many pieces there are, so
    there's never a leftover or a blank cell to worry about here.

    scale < 1.0 shrinks every piece uniformly first, as far as needed for
    cols*rows of them to actually fit the printer's width — the same
    "clamp to whatever the printer can do" rule _place_content_in_cell
    already applies to a single un-packed piece (down to 384px for the
    "A6" hardware line's own A5 output, a much bigger cut than packing
    usually needs). There's no refuse-to-pack threshold: a group always
    packs, same as a single piece always renders — the print is just
    smaller if the printer is narrow, never split back into unpacked
    pieces over it."""
    if scale < 1.0:
        pieces = [
            piece.resize(
                (max(1, round(piece.width * scale)), max(1, round(piece.height * scale))),
                PIL.Image.Resampling.LANCZOS,
            )
            for piece in pieces
        ]
    piece_width_px, piece_height_px = pieces[0].size
    sheet = PIL.Image.new("L", (piece_width_px * cols, piece_height_px * rows), color=255)
    for index, piece in enumerate(pieces):
        col, row = index % cols, index // cols
        sheet.paste(piece, (col * piece_width_px, row * piece_height_px))

    draw = PIL.ImageDraw.Draw(sheet)
    for col in range(1, cols):
        x = col * piece_width_px
        _draw_dashed_line(draw, ((x, 0), (x, sheet.height)))
    for row in range(1, rows):
        y = row * piece_height_px
        _draw_dashed_line(draw, ((0, y), (sheet.width, y)))
    return sheet


def _pack_tiles_for_printing(
    tiles: list[PIL.Image.Image], page_format: PageFormat, width_px: int
) -> list[PIL.Image.Image]:
    """docs/imposition-spec.md §4/§Б.4b — groups every tile of a HALF/
    QUARTER document into capacity_for(page_format)-sized sheets
    (build_sheets), then composes *each* sheet — including a trailing
    partial one — into one physical print pass via _compose_print_sheet().
    A partial sheet is packed into a *compact* shape sized to its actual
    item count (compact_grid_shape), not padded out to the format's full
    grid with blank cells: Paperi prints onto a continuous roll with no
    physical sheet boundary forcing that waste (unlike the ТЗ's own
    sheet-fed/cut-roll model — docs/imposition-spec.md §0), so e.g. 2
    copies of QUARTER (A6, capacity 4) pack into a compact 2x1, not a 2x2
    with 2 blank quadrants — the user's explicit call, since padding blank
    cells here would only waste tape for no benefit on this hardware.

    Before this, a partial group (anything short of capacity_for(page_
    format)) silently fell back to one un-packed page per tile instead of
    packing together at all — inconsistent (N copies behaved differently
    depending on whether N was an exact multiple of capacity) and never
    showed a real grid/cut-line in the preview for anything but an
    exactly-full group. All tiles of a given HALF/QUARTER page_format
    share exactly one pixel size (GridConfig is fixed regardless of
    content — see _place_content_in_cell), so there's no mixed-size
    fallback to handle, unlike before this rewrite.

    NATIVE/CUSTOM have no fixed grid capacity (see capacity_for) and are
    always returned unpacked.

    width_px here is the packing budget the caller decides to trust —
    render_document() passes the printer's real native row width (e.g.
    1728 for A40, verified in Stage 0 against actual hardware and
    matching peripage.PrinterType's own row_width), not the more
    conservative safe_content_width_px (1664 for A40, inferred from a
    single unconfirmed byte in one Bluetooth trace — see
    printer_specs.py's own TODO). A single, un-packed piece still renders
    at the conservative width; only packing trusts the documented one."""
    if page_format not in (PageFormat.HALF, PageFormat.QUARTER) or not tiles:
        return tiles

    packed: list[PIL.Image.Image] = []
    for sheet in build_sheets(tiles, format_of=lambda _tile: page_format):
        cols, rows = compact_grid_shape(page_format, len(sheet.items))
        piece_width_px, _piece_height_px = sheet.items[0].size
        scale = min(1.0, width_px / (piece_width_px * cols))
        packed.append(_compose_print_sheet(list(sheet.items), cols, rows, scale))
    return packed


def _pad_to_canvas_width(image: PIL.Image.Image, canvas_width_px: int) -> PIL.Image.Image:
    """Widens (never stretches) content to canvas_width_px by padding white
    on the right. Needed because printer.printImage() unconditionally
    resizes its input to the model's full native width — feeding it
    anything narrower would silently *stretch* content into the unsafe
    zone instead of leaving it blank there (see printer_specs.py)."""
    if image.width >= canvas_width_px:
        return image
    canvas = PIL.Image.new(image.mode, (canvas_width_px, image.height), color=255)
    canvas.paste(image, (0, 0))
    return canvas


class DocumentPipeline:
    def render_document(
        self,
        document: DocumentItem,
        width_px: int,
        chunk_height_px: int,
        canvas_width_px: int | None = None,
    ) -> RenderedDocument:
        renderer = _RENDERERS.get(document.kind)
        if renderer is None:
            raise UnsupportedDocumentKindError(f"No renderer registered for {document.kind}")

        settings = document.settings
        total_pages = _count_pages(document)
        page_indices = parse_page_range(settings.page_range, total_pages)
        raw_pages = renderer.render(
            document.source_path, width_px, settings.fit_mode, page_indices=page_indices
        )
        target_canvas_width = canvas_width_px or width_px

        tiles: list[PIL.Image.Image] = []
        for raw_page in raw_pages:
            for tile in _apply_page_format(raw_page, settings, width_px):
                # Convert to a single-channel mode *before* any white-fill
                # padding: PIL.Image.new(mode, size, color=255) only
                # broadcasts a bare int to every channel for single-channel
                # modes. For "RGB" (the common case — real photos/PDF
                # pages), color=255 fills only the red channel, i.e.
                # produces red, not white — which then converts to a *dark*
                # gray, not blank space. Caught by a test that actually
                # checked the padded pixel's value rather than just image
                # dimensions.
                grayscale = tile.convert("L")
                if settings.page_mode == "content_length":
                    grayscale = trim_to_content_height(grayscale)
                tiles.append(grayscale)

        # N copies (docs/stage5-ux-plan.md M5.2): literally repeating
        # already-rendered tiles *before* packing, so identical copies are
        # just as eligible to be packed side by side as distinct
        # same-shaped source pages would be.
        if settings.copies > 1:
            tiles = tiles * settings.copies

        # 2 A5s / 4 A6s onto one physical print pass when they fit — see
        # _pack_tiles_for_printing's own docstring for why this has to
        # happen here (real pixels PrintJobManager sends), not just as a
        # preview decoration: printing must match what the preview shows.
        #
        # Budget is target_canvas_width (the model's real native row
        # width, e.g. 1728 for A40 — verified in Stage 0 against actual
        # hardware and matches peripage.PrinterType's own row_width), not
        # width_px (safe_content_width_px — for A40 that's 1664, inferred
        # from a single byte in one Bluetooth trace of unconfirmed
        # meaning, see printer_specs.py's own TODO). A generic single
        # piece of content still renders at the conservative width_px;
        # only the packing budget trusts the documented hardware width.
        tiles = _pack_tiles_for_printing(tiles, settings.page_format, target_canvas_width)

        # Keyed by id(tile), not equality: duplicate copies (or repeated
        # un-packed pieces) share the exact same tile object from the
        # `tiles * settings.copies` repetition above, so finishing one
        # (padding/margins/dithering) once and reusing the RenderedPage for
        # its duplicates avoids redundant work — dithering a photo N times
        # for N copies for no reason. Composed sheets from
        # _pack_tiles_for_printing are always fresh objects, so they're
        # never spuriously deduplicated against each other.
        finished_by_tile_id: dict[int, RenderedPage] = {}
        pages = []
        for tile in tiles:
            finished = finished_by_tile_id.get(id(tile))
            if finished is None:
                content_width_px = tile.width
                content_height_px = tile.height
                widened = _pad_to_canvas_width(tile, target_canvas_width)
                padded = _apply_margins(widened, settings)
                normalized = normalize_to_1bit(padded, settings.dithering)
                chunks = slice_into_chunks(normalized, chunk_height_px)
                finished = RenderedPage(
                    image=normalized,
                    chunks=chunks,
                    content_width_px=content_width_px,
                    content_top_px=settings.margin_top_px,
                    content_height_px=content_height_px,
                )
                finished_by_tile_id[id(tile)] = finished
            pages.append(finished)
        return RenderedDocument(pages=pages)
