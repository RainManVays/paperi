from enum import IntEnum, StrEnum


class PrinterModel(StrEnum):
    A6 = "A6"
    A6_PLUS = "A6p"
    A40 = "A40"
    A40_PLUS = "A40p"


class PaperType(IntEnum):
    """Opcode 10ff1003 + value (method B()/"choosePaperType" in the
    official app — see docs/bluetooth-protocol-trace-analysis.md §7.2).
    Likely only relevant to label-class printers, not a plain continuous
    thermal roll like this project's A40, but cheap to support."""

    FOLDED_BLACK_MARK = 1
    CONTINUOUS_ROLL = 2
    ADHESIVE_GAP = 3
    PERFORATED = 4


class DocumentKind(StrEnum):
    IMAGE = "image"
    TEXT = "text"
    MARKDOWN = "markdown"
    PDF = "pdf"


class PageFormat(StrEnum):
    """Imposition — splitting an already-rendered page (full roll width,
    de-facto "A4"-equivalent, see printer_specs.safe_content_width_px) into
    N physically separate, individually-rotated pieces, printed back to
    back with the existing between-page printBreak() as the cut line
    (docs/stage5-ux-plan.md M5.5). Deliberately NOT named A5/A6 — those
    names are already PrinterModel's (a different axis: fixed roll width
    per hardware model, not user-selectable per job); UI labels still say
    "А5"/"А6" since that's the user's own vocabulary."""

    NATIVE = "native"  # today's behavior — no imposition
    HALF = "half"  # 2 pieces ("А5" in the UI)
    QUARTER = "quarter"  # 4 pieces ("А6" in the UI)
    CUSTOM = "custom"  # explicit tile size in mm


class JobStatus(StrEnum):
    QUEUED = "queued"
    RENDERING = "rendering"
    PRINTING = "printing"
    PAUSED_ERROR = "paused_error"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"
