from __future__ import annotations

from dataclasses import dataclass, field

from periprint.models.enums import DocumentKind, PaperType


@dataclass
class PrintSettings:
    concentration: int = 1
    break_px: int = 60
    fit_mode: str = "fit_width"  # fit_width | actual_size | crop
    dithering: bool = True
    margin_top_px: int = 0
    margin_bottom_px: int = 40
    # Sent via PeripageClient.choose_paper_type() once per job (see
    # docs/stage5-ux-plan.md §0.1 — the official app calls this before
    # every print action, not once per connection). Defaults to
    # continuous roll since that's this project's actual paper stock;
    # only matters in practice for label-class printers.
    paper_type: PaperType = PaperType.CONTINUOUS_ROLL
    # periprint-spec.md §3 P1: full_page prints the whole rendered page
    # (e.g. a full A4 height, most of it likely blank) scaled to printer
    # width; content_length trims trailing/leading blank vertical space
    # first (DocumentPipeline / infra/renderers/base.py::
    # trim_to_content_height) to save tape. Not the same axis as
    # fit_mode, which only controls horizontal scaling.
    page_mode: str = "full_page"  # full_page | content_length


@dataclass
class DocumentItem:
    id: str
    source_path: str
    kind: DocumentKind
    settings: PrintSettings = field(default_factory=PrintSettings)
