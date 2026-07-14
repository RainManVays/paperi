from pathlib import Path

import PIL.Image

from periprint.infra.renderers.image_renderer import ImageRenderer


def test_render_fits_to_target_width(tmp_path: Path) -> None:
    source_path = tmp_path / "source.png"
    PIL.Image.new("RGB", (400, 200), color=(0, 0, 0)).save(source_path)

    pages = ImageRenderer().render(str(source_path), width_px=200, fit_mode="fit_width")

    assert len(pages) == 1
    assert pages[0].width == 200
    assert pages[0].height == 100


def test_render_returns_single_page(tmp_path: Path) -> None:
    source_path = tmp_path / "source.png"
    PIL.Image.new("RGB", (100, 100), color=(255, 255, 255)).save(source_path)

    pages = ImageRenderer().render(str(source_path), width_px=384, fit_mode="fit_width")

    assert len(pages) == 1
