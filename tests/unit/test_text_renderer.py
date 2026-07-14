from pathlib import Path

from periprint.infra.renderers.text_renderer import TextRenderer


def test_render_returns_single_page_at_target_width(tmp_path: Path) -> None:
    source_path = tmp_path / "note.txt"
    source_path.write_text("hello\nworld", encoding="utf-8")

    pages = TextRenderer().render(str(source_path), width_px=384)

    assert len(pages) == 1
    assert pages[0].width == 384
    assert pages[0].mode == "L"


def test_long_line_wraps_and_increases_height(tmp_path: Path) -> None:
    short_path = tmp_path / "short.txt"
    short_path.write_text("hi", encoding="utf-8")

    long_path = tmp_path / "long.txt"
    long_path.write_text("word " * 200, encoding="utf-8")

    renderer = TextRenderer()
    short_page = renderer.render(str(short_path), width_px=384)[0]
    long_page = renderer.render(str(long_path), width_px=384)[0]

    assert long_page.height > short_page.height


def test_empty_file_still_renders_one_line(tmp_path: Path) -> None:
    source_path = tmp_path / "empty.txt"
    source_path.write_text("", encoding="utf-8")

    pages = TextRenderer().render(str(source_path), width_px=384)

    assert len(pages) == 1
    assert pages[0].height > 0
