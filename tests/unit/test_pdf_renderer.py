from pathlib import Path

import fitz

from periprint.infra.renderers.pdf_renderer import PdfRenderer


def _make_pdf(path: Path, page_count: int) -> None:
    document = fitz.open()
    for i in range(page_count):
        page = document.new_page(width=200, height=300)
        page.insert_text((20, 20), f"page {i + 1}")
    document.save(str(path))
    document.close()


def test_render_returns_one_page_per_pdf_page(tmp_path: Path) -> None:
    pdf_path = tmp_path / "doc.pdf"
    _make_pdf(pdf_path, page_count=3)

    pages = PdfRenderer().render(str(pdf_path), width_px=384, fit_mode="fit_width")

    assert len(pages) == 3
    assert all(page.width == 384 for page in pages)


def test_single_page_pdf(tmp_path: Path) -> None:
    pdf_path = tmp_path / "single.pdf"
    _make_pdf(pdf_path, page_count=1)

    pages = PdfRenderer().render(str(pdf_path), width_px=576, fit_mode="fit_width")

    assert len(pages) == 1
    assert pages[0].width == 576
