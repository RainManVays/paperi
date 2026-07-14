from __future__ import annotations

from dataclasses import dataclass, field

from periprint.models.enums import DocumentKind


@dataclass
class PrintSettings:
    concentration: int = 1
    break_px: int = 60
    fit_mode: str = "fit_width"  # fit_width | actual_size | crop
    dithering: bool = True
    margin_top_px: int = 0
    margin_bottom_px: int = 40


@dataclass
class DocumentItem:
    id: str
    source_path: str
    kind: DocumentKind
    settings: PrintSettings = field(default_factory=PrintSettings)
