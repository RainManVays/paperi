import PIL.Image
import PIL.ImageDraw

from paperi.infra.renderers.base import (
    apply_mirror,
    fit_into_frame,
    fit_to_width,
    normalize_to_1bit,
    rotate_page,
    trim_to_content_height,
)


def _image(width: int, height: int = 50, color: int = 128) -> PIL.Image.Image:
    return PIL.Image.new("L", (width, height), color=color)


def test_fit_width_scales_proportionally() -> None:
    result = fit_to_width(_image(width=200, height=100), width_px=100, fit_mode="fit_width")

    assert result.width == 100
    assert result.height == 50


def test_fit_width_no_op_when_already_target_width() -> None:
    source = _image(width=100, height=40)

    result = fit_to_width(source, width_px=100, fit_mode="fit_width")

    assert result.width == 100
    assert result.height == 40


def test_actual_size_pads_narrower_image() -> None:
    result = fit_to_width(_image(width=50, height=30), width_px=100, fit_mode="actual_size")

    assert result.width == 100
    assert result.height == 30


def test_actual_size_crops_wider_image() -> None:
    result = fit_to_width(_image(width=200, height=30), width_px=100, fit_mode="actual_size")

    assert result.width == 100
    assert result.height == 30


def test_crop_mode_center_crops_wider_image() -> None:
    result = fit_to_width(_image(width=300, height=30), width_px=100, fit_mode="crop")

    assert result.width == 100


def test_normalize_to_1bit_with_dithering() -> None:
    image = PIL.Image.new("L", (10, 10), color=128)

    result = normalize_to_1bit(image, dithering=True)

    assert result.mode == "1"
    assert result.size == (10, 10)


def test_normalize_to_1bit_without_dithering_uses_threshold() -> None:
    image = PIL.Image.new("L", (10, 10), color=200)

    result = normalize_to_1bit(image, dithering=False)

    assert result.mode == "1"
    # Above mid-gray threshold with no dithering -> every pixel white (255/on).
    assert result.getpixel((0, 0)) != 0


def test_trim_to_content_height_crops_blank_tail() -> None:
    # A "page" with content only in a band near the top, like a short PDF
    # page rendered at full A4 height (paperi-spec.md §3 P1 "по длине
    # контента" mode).
    image = PIL.Image.new("L", (100, 1000), color=255)
    draw = PIL.ImageDraw.Draw(image)
    draw.rectangle([10, 20, 90, 60], fill=0)

    result = trim_to_content_height(image)

    assert result.width == 100
    # rectangle([10, 20, 90, 60]) draws rows 20-60 inclusive (41 rows);
    # getbbox()'s lower bound is exclusive, so the crop is [20, 61).
    assert result.height == 41
    assert result.getpixel((50, 10)) == 0  # was row 30 in the original


def test_trim_to_content_height_leaves_full_page_untouched() -> None:
    image = PIL.Image.new("L", (100, 1000), color=255)
    draw = PIL.ImageDraw.Draw(image)
    draw.rectangle([10, 20, 90, 60], fill=0)

    # full_page mode never calls trim_to_content_height at all — this just
    # confirms fit_to_width alone (the other axis) doesn't accidentally
    # crop height on its own.
    result = fit_to_width(image, width_px=100, fit_mode="fit_width")

    assert result.height == 1000


def test_trim_to_content_height_blank_page_is_untouched() -> None:
    blank = PIL.Image.new("L", (100, 500), color=255)

    result = trim_to_content_height(blank)

    assert result.height == 500
    assert result.width == 100


def test_rotate_page_zero_degrees_is_a_no_op() -> None:
    source = _image(width=100, height=50)

    result = rotate_page(source, 0)

    assert result is source


def test_rotate_page_90_and_270_swap_dimensions() -> None:
    source = _image(width=100, height=50)

    assert rotate_page(source, 90).size == (50, 100)
    assert rotate_page(source, 270).size == (50, 100)


def test_rotate_page_180_keeps_dimensions_but_flips_content() -> None:
    image = PIL.Image.new("L", (10, 20), color=255)
    image.putpixel((0, 0), 0)  # mark the top-left corner

    result = rotate_page(image, 180)

    assert result.size == (10, 20)
    assert result.getpixel((0, 0)) != 0  # was white
    assert result.getpixel((9, 19)) == 0  # marker moved to the opposite corner


def _asymmetric_image(width: int = 11, height: int = 7) -> PIL.Image.Image:
    # A per-pixel-unique pattern, not just a single marker pixel — proves
    # full pixel-for-pixel equality/inequality, not just "the one corner I
    # happened to check matches" (docs/imposition-spec.md §10 + the
    # 61217b4 postmortem: a test that only checks one landmark can pass on
    # a genuinely wrong transform).
    image = PIL.Image.new("L", (width, height))
    for y in range(height):
        for x in range(width):
            image.putpixel((x, y), (x * 13 + y * 7) % 256)
    return image


def test_mirror_neither_axis_is_a_no_op() -> None:
    source = _image(width=10, height=20)

    assert apply_mirror(source, horizontal=False, vertical=False) is source


def test_mirror_horizontal_flips_left_right() -> None:
    image = PIL.Image.new("L", (4, 2), color=255)
    image.putpixel((0, 0), 0)

    result = apply_mirror(image, horizontal=True, vertical=False)

    assert result.getpixel((3, 0)) == 0
    assert result.getpixel((0, 0)) == 255


def test_mirror_vertical_flips_top_bottom() -> None:
    image = PIL.Image.new("L", (4, 2), color=255)
    image.putpixel((0, 0), 0)

    result = apply_mirror(image, horizontal=False, vertical=True)

    assert result.getpixel((0, 1)) == 0
    assert result.getpixel((0, 0)) == 255


def test_mirror_both_axes_equals_rotate_180_pixelwise() -> None:
    # docs/imposition-spec.md §6.1 / §10: flipping both axes must be
    # pixel-identical to a 180° rotation — a mathematical identity, not
    # coincidence, and the spec explicitly allows (but doesn't require)
    # optimizing this case as long as behavior matches.
    image = _asymmetric_image()

    mirrored = apply_mirror(image, horizontal=True, vertical=True)
    rotated = rotate_page(image, 180)

    assert list(mirrored.getdata()) == list(rotated.getdata())


def test_mirror_single_axis_is_not_equivalent_to_rotate_180() -> None:
    # The opposite side of the same coin: mirroring is not rotation —
    # flipping only one axis reverses chirality (text reads backwards)
    # while a rotation never does, so single-axis mirror must differ from
    # rotate_page(image, 180) pixelwise.
    image = _asymmetric_image()
    rotated_data = list(rotate_page(image, 180).getdata())

    assert list(apply_mirror(image, horizontal=True, vertical=False).getdata()) != rotated_data
    assert list(apply_mirror(image, horizontal=False, vertical=True).getdata()) != rotated_data


def test_fit_into_frame_matching_aspect_ratio_has_no_letterbox() -> None:
    # ISO 216: A5 (148x210mm) is an exact half of A4 — content already
    # prepared at the frame's own aspect ratio must fill it edge to edge,
    # not get shrunk further or padded.
    source = _image(width=148, height=210, color=0)  # solid black, frame-shaped

    result = fit_into_frame(source, frame_width_px=148, frame_height_px=210)

    assert result.size == (148, 210)
    assert result.getpixel((0, 0)) == 0
    assert result.getpixel((147, 209)) == 0


def test_fit_into_frame_letterboxes_narrower_content_horizontally() -> None:
    # Content taller (relative to its width) than the frame -> height is
    # the binding constraint, so it's centered with white bars left/right.
    source = _image(width=50, height=200, color=0)

    result = fit_into_frame(source, frame_width_px=100, frame_height_px=100)

    assert result.size == (100, 100)
    # scale = min(100/50, 100/200) = 0.5 -> content becomes 25x100,
    # centered at x=[37, 62); columns outside that are blank white.
    assert result.getpixel((0, 50)) == 255
    assert result.getpixel((50, 50)) == 0
    assert result.getpixel((99, 50)) == 255


def test_fit_into_frame_letterboxes_shorter_content_vertically() -> None:
    # Content wider (relative to its height) than the frame -> width is
    # the binding constraint, white bars appear on top/bottom instead.
    source = _image(width=200, height=50, color=0)

    result = fit_into_frame(source, frame_width_px=100, frame_height_px=100)

    assert result.size == (100, 100)
    assert result.getpixel((50, 0)) == 255
    assert result.getpixel((50, 50)) == 0
    assert result.getpixel((50, 99)) == 255


def test_fit_into_frame_never_crops_or_overflows_either_axis() -> None:
    # A source far more extreme in aspect ratio than the frame must still
    # land entirely inside it — no cropping, regardless of shape.
    source = _image(width=2000, height=10, color=0)

    result = fit_into_frame(source, frame_width_px=100, frame_height_px=100)

    assert result.size == (100, 100)


def test_fit_into_frame_pads_rgb_images_with_true_white_not_red() -> None:
    # Regression test: PIL.Image.new("RGB", size, color=255) only fills the
    # red channel, producing dark gray/red padding instead of white for any
    # RGB source (real photos, most PDF pages) — see _white_fill().
    source = PIL.Image.new("RGB", (50, 200), color=(0, 0, 0))

    result = fit_into_frame(source, frame_width_px=100, frame_height_px=100)

    assert result.getpixel((0, 50)) == (255, 255, 255)


def test_actual_size_pads_rgb_images_with_true_white_not_red() -> None:
    # Same regression as above, for fit_to_width's own padding branch.
    source = PIL.Image.new("RGB", (50, 30), color=(0, 0, 0))

    result = fit_to_width(source, width_px=100, fit_mode="actual_size")

    assert result.getpixel((0, 0)) == (255, 255, 255)
