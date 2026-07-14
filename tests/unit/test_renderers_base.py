import PIL.Image

from periprint.infra.renderers.base import fit_to_width, normalize_to_1bit


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
