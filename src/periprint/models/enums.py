from enum import StrEnum


class PrinterModel(StrEnum):
    A6 = "A6"
    A6_PLUS = "A6p"
    A40 = "A40"
    A40_PLUS = "A40p"


class DocumentKind(StrEnum):
    IMAGE = "image"
    TEXT = "text"
    MARKDOWN = "markdown"
    PDF = "pdf"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RENDERING = "rendering"
    PRINTING = "printing"
    PAUSED_ERROR = "paused_error"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"
