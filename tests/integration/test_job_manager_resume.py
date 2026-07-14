import queue
import uuid
from pathlib import Path

import pytest

from periprint.infra.peripage_client import PeripageClient
from periprint.models.document import DocumentItem
from periprint.models.enums import DocumentKind, JobStatus, PrinterModel
from periprint.models.job import PrintJob
from periprint.services import job_manager as job_manager_module
from periprint.services.job_manager import PrintJobManager
from periprint.services.pipeline import DocumentPipeline
from tests.integration.fakes.fake_raw_printer import FakeRawPrinter


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(job_manager_module.time, "sleep", lambda seconds: None)


def _make_text_document(tmp_path: Path, lines: int = 40) -> DocumentItem:
    path = tmp_path / "note.txt"
    path.write_text("\n".join(f"line {i}" for i in range(lines)), encoding="utf-8")
    return DocumentItem(id=str(uuid.uuid4()), source_path=str(path), kind=DocumentKind.TEXT)


def _connected_client(fake: FakeRawPrinter) -> PeripageClient:
    client = PeripageClient(
        mac="AA:BB:CC:DD:EE:FF",
        model=PrinterModel.A40,
        printer_factory=lambda mac, model: fake,
    )
    client.connect()
    return client


def test_job_completes_successfully(tmp_path: Path) -> None:
    fake = FakeRawPrinter()
    client = _connected_client(fake)
    event_queue: queue.Queue = queue.Queue()
    manager = PrintJobManager(DocumentPipeline(), event_queue, client_provider=lambda: client)

    document = _make_text_document(tmp_path)
    job = PrintJob(id=str(uuid.uuid4()), document=document, printer_profile_id="p1")
    manager.enqueue(job, width_px=384, chunk_height_px=30)
    manager._process_job(job)

    assert job.status == JobStatus.DONE
    assert job.total_chunks > 1
    assert job.completed_chunks == job.total_chunks
    assert fake.print_image_calls == job.total_chunks


def test_mid_job_failure_pauses_without_losing_progress(tmp_path: Path) -> None:
    fake = FakeRawPrinter()
    fake.fail_print_image_on_call = 3  # fail on the 3rd printImage() call
    client = _connected_client(fake)
    event_queue: queue.Queue = queue.Queue()
    manager = PrintJobManager(DocumentPipeline(), event_queue, client_provider=lambda: client)

    document = _make_text_document(tmp_path)
    job = PrintJob(id=str(uuid.uuid4()), document=document, printer_profile_id="p1")
    manager.enqueue(job, width_px=384, chunk_height_px=30)
    manager._process_job(job)

    assert job.status == JobStatus.PAUSED_ERROR
    assert job.completed_chunks == 2  # chunks 1 and 2 succeeded before the 3rd failed
    assert fake.print_image_calls == 3
    total_chunks = job.total_chunks

    # Simulate the app's reconnect/retry path (mirrors what
    # PrintJobManager.retry_job does, minus spawning the worker thread —
    # avoiding that keeps this test deterministic instead of racing a
    # background thread against the assertions below).
    fake.fail_print_image_on_call = None
    job.status = JobStatus.QUEUED
    job.error_message = None
    manager._process_job(job)

    assert job.status == JobStatus.DONE
    assert job.completed_chunks == total_chunks
    # Resume must not re-send the 2 chunks already completed before the
    # failure: 3 calls before (2 succeeded + 1 failed) + remaining chunks.
    assert fake.print_image_calls == 3 + (total_chunks - 2)


def test_job_paused_when_printer_not_connected(tmp_path: Path) -> None:
    event_queue: queue.Queue = queue.Queue()
    manager = PrintJobManager(DocumentPipeline(), event_queue, client_provider=lambda: None)

    document = _make_text_document(tmp_path)
    job = PrintJob(id=str(uuid.uuid4()), document=document, printer_profile_id="p1")
    manager.enqueue(job, width_px=384, chunk_height_px=30)
    manager._process_job(job)

    assert job.status == JobStatus.PAUSED_ERROR
    assert job.completed_chunks == 0


def test_multi_page_document_gets_page_break_between_pages(tmp_path: Path) -> None:
    import fitz

    pdf_path = tmp_path / "doc.pdf"
    document_handle = fitz.open()
    for i in range(2):
        page = document_handle.new_page(width=200, height=300)
        page.insert_text((20, 20), f"page {i + 1}")
    document_handle.save(str(pdf_path))
    document_handle.close()

    fake = FakeRawPrinter()
    client = _connected_client(fake)
    event_queue: queue.Queue = queue.Queue()
    manager = PrintJobManager(DocumentPipeline(), event_queue, client_provider=lambda: client)

    document = DocumentItem(id=str(uuid.uuid4()), source_path=str(pdf_path), kind=DocumentKind.PDF)
    job = PrintJob(id=str(uuid.uuid4()), document=document, printer_profile_id="p1")
    manager.enqueue(job, width_px=384, chunk_height_px=100)
    manager._process_job(job)

    assert job.status == JobStatus.DONE
    # One printBreak between the 2 pages, plus one trailing tear-off break.
    assert fake.print_break_calls == 2
