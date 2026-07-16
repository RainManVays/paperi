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
    """Target frame size each rendered page is imposed into via a true 2D
    scale-to-fit ("object-fit: contain"): scaled by
    min(frame_width/content_width, frame_height/content_height), centered,
    letterboxed with white on whichever axis has slack — never cropped,
    never scaled past what fits both dimensions (docs/stage5-ux-plan.md
    M5.5 postmortem #4: an earlier crop-based design sliced a landscape
    photo in half instead of shrinking it; a later width-only-scale design
    paginated tall content across multiple pieces instead of fitting it
    into one frame). ISO 216 makes A5/A6 exact fractions of A4 (halving the
    long side each step, preserving √2:1), so content already prepared at
    the target size fills its frame edge to edge with no visible letterbox.
    Each source page becomes exactly one physical piece — a multi-page PDF
    already supplies one piece per page, no further splitting happens
    here. The frame's own orientation follows the page's actual shape
    *after* rotation, not just a rotation_degrees special case: a
    landscape photo gets a landscape 210x148mm frame even at 0° rotation,
    and rotating a page 90°/270° flips the frame the same way by changing
    that shape — never sideways or landscape content squeezed into a
    frame that stayed the nominal portrait shape (see
    pipeline.py::_apply_page_format). Deliberately NOT named A5/A6 — those
    names are already PrinterModel's (a different axis: fixed roll width
    per hardware model, not
    user-selectable per job); UI labels still say "А5"/"А6" since that's
    the user's own vocabulary."""

    NATIVE = "native"  # today's behavior — no imposition, fills the roll width
    HALF = "half"  # target width/height = real A5 (148x210mm)
    QUARTER = "quarter"  # target width/height = real A6 (105x148mm)
    CUSTOM = "custom"  # explicit tile size in mm


class Orientation(StrEnum):
    """Three-valued (not a bare width>height bool) per docs/imposition-spec.md
    §6.2: a bool comparison silently buckets a square shape into PORTRAIT,
    which happens to look right until auto-rotation logic starts branching
    on it. SQUARE gets its own explicit branch (auto rotation is a no-op —
    rotating a square changes nothing) instead of an accidental one."""

    LANDSCAPE = "landscape"
    PORTRAIT = "portrait"
    SQUARE = "square"


class ResidualStripPolicy(StrEnum):
    """Where the ISO 216 rounding remainder (1mm for A5/A6 — two 148mm
    tiles are 296mm, not the nominal 297mm sheet height) is placed within
    the grid's fixed 297mm canvas — see docs/imposition-spec.md §5.1.
    Purely a geometry input to services/grid.py; has no visible effect on
    Peripage output today (no fixed-length physical sheet, no cutter), but
    keeping it explicit avoids baking TRAILING in as an unstated
    assumption for whenever ROLL_CONTINUOUS needs real cumulative offsets."""

    LEADING = "leading"
    TRAILING = "trailing"
    CENTERED = "centered"
    DISTRIBUTED = "distributed"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RENDERING = "rendering"
    PRINTING = "printing"
    PAUSED_ERROR = "paused_error"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"
