import PIL.Image
import pytest

from periprint.infra.renderers.base import slice_into_chunks


def _image(height: int, width: int = 100) -> PIL.Image.Image:
    return PIL.Image.new("L", (width, height), color=255)


def test_exact_multiple_of_chunk_height() -> None:
    chunks = slice_into_chunks(_image(height=600), chunk_height_px=200)

    assert len(chunks) == 3
    assert all(chunk.height == 200 for chunk in chunks)


def test_remainder_produces_shorter_last_chunk() -> None:
    chunks = slice_into_chunks(_image(height=650), chunk_height_px=200)

    assert len(chunks) == 4
    assert [c.height for c in chunks] == [200, 200, 200, 50]


def test_image_shorter_than_one_chunk() -> None:
    chunks = slice_into_chunks(_image(height=50), chunk_height_px=200)

    assert len(chunks) == 1
    assert chunks[0].height == 50


def test_zero_height_image_returns_no_chunks() -> None:
    chunks = slice_into_chunks(_image(height=0), chunk_height_px=200)

    assert chunks == []


def test_non_positive_chunk_height_raises() -> None:
    with pytest.raises(ValueError):
        slice_into_chunks(_image(height=100), chunk_height_px=0)

    with pytest.raises(ValueError):
        slice_into_chunks(_image(height=100), chunk_height_px=-10)


def test_chunk_width_matches_source_width() -> None:
    chunks = slice_into_chunks(_image(height=300, width=384), chunk_height_px=100)

    assert all(chunk.width == 384 for chunk in chunks)
