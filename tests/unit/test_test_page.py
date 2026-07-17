import PIL.Image

from paperi.models.enums import PrinterModel
from paperi.services.test_page import generate_test_page


def _generate(width_px: int = 384, canvas_width_px: int = 384) -> PIL.Image.Image:
    return generate_test_page(
        model=PrinterModel.A6,
        content_width_px=width_px,
        canvas_width_px=canvas_width_px,
        profile_name="Тестовый принтер",
        mac="28:D4:1E:01:34:C4",
        concentration=2,
    )


def test_generate_test_page_matches_requested_width() -> None:
    image = _generate(width_px=384)

    assert image.mode == "L"
    assert image.width == 384


def test_generate_test_page_is_cropped_to_actual_content_not_the_full_scratch_canvas() -> None:
    image = _generate()

    # Well under the 4000px scratch canvas the page is drawn into, and non-
    # trivially tall (there's a lot of content) — pins down that the crop
    # in generate_test_page() actually ran instead of returning the raw
    # oversized canvas.
    assert 800 < image.height < 3000


def test_generate_test_page_is_not_blank() -> None:
    image = _generate()

    histogram = image.histogram()
    total_pixels = image.width * image.height
    white_pixels = histogram[255]
    assert white_pixels < total_pixels


def test_generate_test_page_scales_with_a_wider_printer() -> None:
    narrow = _generate(width_px=384, canvas_width_px=384)
    wide = _generate(width_px=1664, canvas_width_px=1728)

    assert wide.width == 1664
    assert narrow.width == 384


def test_generate_test_page_contains_a_full_width_solid_black_bar() -> None:
    """The solid-fill section is meant to turn a dead printhead element
    into an unbroken vertical gap in an otherwise all-black row — that only
    works if the row really is fully black edge to edge."""
    image = _generate()
    pixels = image.load()

    solid_rows = 0
    for y in range(image.height):
        if all(pixels[x, y] == 0 for x in range(image.width)):
            solid_rows += 1
    assert solid_rows > 0
