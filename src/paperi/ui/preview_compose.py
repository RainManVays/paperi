import PIL.Image
import PIL.ImageDraw

from paperi.models.printer_specs import PRINT_DPI

# ISO 216 portrait A4 — used purely as a visual scale reference in the
# preview; the printer itself is a continuous thermal roll with no real
# page boundary. This exists only to give the user intuition for how big a
# physical A5/A6/custom-format piece is next to standard paper (A4=2xA5
# exactly, by construction of ISO 216 — see PageFormat's docstring).
# Always portrait — never swapped to landscape for wide/landscape-shaped
# content (docs/imposition-spec.md §Б.4f, the user's own explicit call):
# the preview page should always read as a normal, upright sheet, not
# flip orientation depending on what's on it.
_A4_PORTRAIT_MM = (210.0, 297.0)


def compose_a4_mockup(
    image: PIL.Image.Image,
    content_width_px: int,
    content_top_px: int = 0,
    content_height_px: int | None = None,
) -> PIL.Image.Image:
    """Draws the true imposed content — image cropped to content_width_px
    horizontally and to [content_top_px, content_top_px+content_height_px)
    vertically, dropping the blank canvas-width padding
    _pad_to_canvas_width added and the margin_top_px/margin_bottom_px
    tear-off feed allowance _apply_margins added — at its real physical
    size, against an outlined nominal-A4 reference sheet. Content and the
    A4 outline share the same PRINT_DPI calibration, so 1 content px == 1
    mockup px, making the comparison accurate.

    content_height_px=None (the default) skips the vertical crop
    entirely, using the image as tall as it already is from
    content_top_px down.

    Excluding the tear-off margin matters (docs/imposition-spec.md
    §Б.4g): it's a printer feed allowance, not real content, so including
    it in the "does this fit on one A4" comparison made the mockup's
    white margin visibly poke out a few mm past the drawn A4 outline for
    no informative reason — neither "your content is too big for A4" nor
    an intentional callout of the tear-off allowance, just confusing.

    When DocumentPipeline packed multiple physical pieces (2 A5s, 4 A6s,
    or any compact partial group — pipeline.py::_pack_tiles_for_printing)
    into one print pass, `image` is already that composited sheet, dashed
    cut guides and all — this function just displays whatever will
    actually be printed, it doesn't do any grouping of its own. That's
    what keeps the preview honest: what you see here is the same pixels
    PrintJobManager sends.

    Content taller or wider than the portrait outline simply extends past
    it instead of being clipped or shrunk — the overflow itself is useful
    information ("this won't fit on a real A4 sheet")."""
    bottom = image.height if content_height_px is None else content_top_px + content_height_px
    content = image.crop(
        (0, content_top_px, min(content_width_px, image.width), min(bottom, image.height))
    )

    a4_width_mm, a4_height_mm = _A4_PORTRAIT_MM
    a4_width_px = round(a4_width_mm * PRINT_DPI / 25.4)
    a4_height_px = round(a4_height_mm * PRINT_DPI / 25.4)
    canvas_width = max(a4_width_px, content.width)
    canvas_height = max(a4_height_px, content.height)

    canvas = PIL.Image.new("RGB", (canvas_width, canvas_height), color=(255, 255, 255))
    # Convert through "L" even for already-grayscale/1-bit content so a
    # later downscale-to-fit-the-preview-widget averages dithered dots into
    # smooth gray instead of aliasing them (see PreviewPanel._refresh_preview_fit).
    canvas.paste(content.convert("L").convert("RGB"), (0, 0))

    # Drawn *after* pasting content, not before: content is opaque, so an
    # outline drawn first gets silently erased wherever content covers it
    # (the whole left edge, whenever content reaches all the way to x=0,
    # which it always does) and only survives where content falls short of
    # the canvas — e.g. the blank area below a short photo, or the sliver
    # to the right when content_width_px < a4_width_px. That asymmetry is
    # exactly what read as a "side margin": a solid gray bar appearing out
    # of nowhere the instant content stops, not a thin, consistent page
    # outline. Drawing on top makes the frame uniform on all four sides
    # regardless of what's under it, at the cost of the outline covering
    # the outermost couple of content pixels if content reaches the very
    # edge — a far smaller visual cost than the bar it replaces.
    #
    # The preview widget typically displays this shrunk by 5-10x, so the
    # stroke needs to stay comfortably above 1px post-scale-down or it
    # disappears into anti-aliasing.
    border_px = max(4, a4_width_px // 120)
    PIL.ImageDraw.Draw(canvas).rectangle(
        [0, 0, a4_width_px - 1, a4_height_px - 1], outline=(120, 120, 120), width=border_px
    )
    return canvas
