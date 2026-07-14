from dataclasses import dataclass
from pathlib import Path

import PIL.Image

from periprint.infra.renderers.base import Renderer, normalize_to_1bit, slice_into_chunks
from periprint.infra.renderers.image_renderer import ImageRenderer
from periprint.infra.renderers.pdf_renderer import PdfRenderer
from periprint.infra.renderers.text_renderer import TextRenderer
from periprint.models.document import DocumentItem, PrintSettings
from periprint.models.enums import DocumentKind

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


class UnsupportedDocumentKindError(Exception):
    pass


def detect_document_kind(source_path: str) -> DocumentKind | None:
    return _EXTENSION_TO_KIND.get(Path(source_path).suffix.lower())


@dataclass
class RenderedPage:
    image: PIL.Image.Image  # normalized 1-bit, full page — for preview
    chunks: list[PIL.Image.Image]  # same image sliced by chunk_height_px


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


class DocumentPipeline:
    def render_document(
        self, document: DocumentItem, width_px: int, chunk_height_px: int
    ) -> RenderedDocument:
        renderer = _RENDERERS.get(document.kind)
        if renderer is None:
            raise UnsupportedDocumentKindError(f"No renderer registered for {document.kind}")

        settings = document.settings
        raw_pages = renderer.render(document.source_path, width_px, settings.fit_mode)

        pages = []
        for raw_page in raw_pages:
            padded = _apply_margins(raw_page, settings)
            normalized = normalize_to_1bit(padded, settings.dithering)
            chunks = slice_into_chunks(normalized, chunk_height_px)
            pages.append(RenderedPage(image=normalized, chunks=chunks))
        return RenderedDocument(pages=pages)
