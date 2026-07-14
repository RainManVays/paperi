from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from periprint.models.document import DocumentItem
from periprint.models.enums import JobStatus


@dataclass
class PrintJob:
    id: str
    document: DocumentItem
    printer_profile_id: str
    status: JobStatus = JobStatus.QUEUED
    total_chunks: int = 0
    completed_chunks: int = 0
    error_message: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
