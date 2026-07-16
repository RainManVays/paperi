import PIL.Image

from periprint.ui.preview_compose import compose_a4_mockup

# A4 portrait @ PRINT_DPI=203: 210mm -> 1678px, 297mm -> 2374px. The
# reference sheet is always this shape now — never swapped to landscape.
_A4_PORTRAIT_PX = (1678, 2374)


def test_compose_a4_mockup_frame_is_drawn_on_top_of_content() -> None:
    """docs/imposition-spec.md §Б.4h — the real bug the user spotted
    ("боковые отступы"): content is opaque, so an outline drawn *before*
    pasting it gets silently erased everywhere content covers it (the
    left edge always, since content always starts at x=0) and only
    survives where content falls short of the canvas (a short photo's
    blank area below it, or a narrower-than-A4 piece's right-hand
    sliver) — a solid gray bar appearing to spring out of nowhere right
    where content stops, not a thin, consistent page outline. Drawing the
    frame *after* pasting makes it uniform on all four sides regardless
    of content — visible at the very edge even where content reaches
    all the way there, just like a real printed page border would be."""
    # Short, wide content that leaves blank space below and to the right
    # of a full 210x297mm reference — exactly the shape that exposed the
    # asymmetry.
    image = PIL.Image.new("L", (1600, 500), color=0)

    result = compose_a4_mockup(image, content_width_px=1600)

    border_px = max(4, 1678 // 120)
    mid_row = 250  # inside the content vertically
    # Left edge: previously white (erased by the opaque paste); now gray.
    assert result.getpixel((border_px // 2, mid_row)) == (120, 120, 120)
    # Right edge, within content rows: content (1600) falls short of the
    # full A4 width (1678) by more than one border width, so this was
    # already gray before the fix too — still must be, not accidentally
    # broken by the reordering.
    assert result.getpixel((1678 - border_px // 2 - 1, mid_row)) == (120, 120, 120)


def test_compose_a4_mockup_crops_to_content_width_before_sizing() -> None:
    # A wide, short image (as if already padded out to the printer's full
    # canvas width by _pad_to_canvas_width) but a narrow, tall
    # content_width_px — the real content is portrait-shaped, and the
    # mockup must pick the A4 orientation off the *cropped* shape, not the
    # padded canvas.
    image = PIL.Image.new("L", (2000, 100), color=0)

    result = compose_a4_mockup(image, content_width_px=100)

    assert result.size == _A4_PORTRAIT_PX


def test_compose_a4_mockup_stays_portrait_for_wide_content() -> None:
    # The reference sheet never flips to landscape, even for wide/
    # landscape-shaped content (the user's own explicit call: the preview
    # page should always read as a normal upright sheet) — wide content
    # just extends past the portrait outline's width instead.
    image = PIL.Image.new("L", (200, 100), color=0)

    result = compose_a4_mockup(image, content_width_px=200)

    assert result.size == _A4_PORTRAIT_PX


def test_compose_a4_mockup_overflow_extends_past_a4_instead_of_shrinking() -> None:
    # Content bigger than A4 in both directions must remain full size,
    # extending past the drawn outline rather than being clipped/scaled —
    # seeing that overflow is itself useful information.
    image = PIL.Image.new("L", (3000, 3000), color=0)

    result = compose_a4_mockup(image, content_width_px=3000)

    assert result.size == (3000, 3000)


def test_compose_a4_mockup_pastes_content_at_the_origin() -> None:
    # Larger than the border stroke's own width (see
    # test_compose_a4_mockup_frame_is_drawn_on_top_of_content) so this
    # checks a pixel that's genuinely content, not the frame overlapping
    # a content region too small to tell the difference.
    image = PIL.Image.new("L", (100, 100), color=0)

    result = compose_a4_mockup(image, content_width_px=100)

    assert result.getpixel((50, 50)) == (0, 0, 0)


def test_compose_a4_mockup_background_is_true_white() -> None:
    image = PIL.Image.new("L", (10, 10), color=0)

    result = compose_a4_mockup(image, content_width_px=10)

    # Far from both the content and the border stroke — deep interior of
    # the A4 sheet — must be plain white.
    assert result.getpixel((800, 800)) == (255, 255, 255)


def test_compose_a4_mockup_shows_an_already_packed_sheet_as_is() -> None:
    # DocumentPipeline may already have packed 2 A5s / 4 A6s into one wide
    # image (pipeline.py::_pack_tiles_for_printing) before this ever runs
    # — compose_a4_mockup just displays whatever it's given, with no
    # grouping of its own, so a packed sheet's own internal cut guide
    # (drawn by the pipeline) shows through untouched. Reference height
    # stays the portrait 2374px even though this particular packed sheet
    # is landscape-shaped; its width (2366px) is wider than the portrait
    # outline's own 1678px, so it extends past it on the width axis
    # instead of forcing a landscape swap.
    packed_sheet = PIL.Image.new("L", (1183 * 2, 1678), color=0)

    result = compose_a4_mockup(packed_sheet, content_width_px=1183 * 2)

    assert result.size == (1183 * 2, _A4_PORTRAIT_PX[1])
    # Past the frame's own border width (see
    # test_compose_a4_mockup_frame_is_drawn_on_top_of_content) on both
    # sides of the pipeline's own cut-line seam.
    assert result.getpixel((20, 20)) == (0, 0, 0)
    assert result.getpixel((1183 + 20, 20)) == (0, 0, 0)


def test_compose_a4_mockup_excludes_bottom_margin_from_content_height() -> None:
    # docs/imposition-spec.md §Б.4g: the real content is 100px tall, plus
    # a 40px tear-off margin _apply_margins tacked onto the bottom (140px
    # total in `image`) — content_height_px=100 must crop that margin
    # away so it doesn't factor into the "does this fit on A4" comparison
    # (previously it made the mockup's white margin visibly poke out past
    # the drawn A4 outline for no informative reason).
    image = PIL.Image.new("L", (100, 140), color=0)

    result = compose_a4_mockup(image, content_width_px=100, content_height_px=100)

    assert result.size == _A4_PORTRAIT_PX


def test_compose_a4_mockup_excludes_top_margin_via_content_top_px() -> None:
    # margin_top_px (default 0, but settable) shifts real content down
    # within `image` — content_top_px must skip past it, not include it
    # as part of the cropped content.
    image = PIL.Image.new("L", (100, 130), color=255)
    marker = PIL.Image.new("L", (100, 100), color=0)
    image.paste(marker, (0, 30))  # content starts at y=30 (margin_top_px=30)

    result = compose_a4_mockup(
        image, content_width_px=100, content_top_px=30, content_height_px=100
    )

    # A point inside the marker but past the frame's own border width
    # (see test_compose_a4_mockup_frame_is_drawn_on_top_of_content) should
    # be the marker's black, not the margin's white.
    assert result.getpixel((50, 50)) == (0, 0, 0)


def test_compose_a4_mockup_no_content_height_uses_full_remaining_image() -> None:
    # content_height_px=None (the default) skips the vertical crop
    # entirely — existing callers that don't track a separate content
    # height still see the whole image.
    image = PIL.Image.new("L", (100, 100), color=0)

    result = compose_a4_mockup(image, content_width_px=100)

    assert result.size == _A4_PORTRAIT_PX
