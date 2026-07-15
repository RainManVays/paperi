import queue
import uuid

import pytest

from periprint.models.document import DocumentItem
from periprint.models.enums import DocumentKind, JobStatus
from periprint.models.job import PrintJob
from periprint.services.job_manager import PrintJobManager


def _make_job(status: JobStatus = JobStatus.QUEUED) -> PrintJob:
    document = DocumentItem(id=str(uuid.uuid4()), source_path="/dev/null", kind=DocumentKind.TEXT)
    job = PrintJob(id=str(uuid.uuid4()), document=document, printer_profile_id="p1")
    job.status = status
    return job


@pytest.fixture
def manager() -> PrintJobManager:
    # None/None: these tests never call _process_job()/start(), only pure
    # queue bookkeeping — no pipeline or printer client needed at all.
    return PrintJobManager(None, queue.Queue(), client_provider=lambda: None)  # type: ignore[arg-type]


def _ids(manager: PrintJobManager) -> list[str]:
    return [job.id for job in manager.list_jobs()]


def test_move_job_up_swaps_with_previous(manager: PrintJobManager) -> None:
    jobs = [_make_job() for _ in range(3)]
    for job in jobs:
        manager.enqueue(job, width_px=100, chunk_height_px=100)

    manager.move_job(jobs[2].id, delta=-1)

    assert _ids(manager) == [jobs[0].id, jobs[2].id, jobs[1].id]


def test_move_job_down_swaps_with_next(manager: PrintJobManager) -> None:
    jobs = [_make_job() for _ in range(3)]
    for job in jobs:
        manager.enqueue(job, width_px=100, chunk_height_px=100)

    manager.move_job(jobs[0].id, delta=1)

    assert _ids(manager) == [jobs[1].id, jobs[0].id, jobs[2].id]


def test_move_job_at_front_is_a_no_op(manager: PrintJobManager) -> None:
    jobs = [_make_job() for _ in range(2)]
    for job in jobs:
        manager.enqueue(job, width_px=100, chunk_height_px=100)

    manager.move_job(jobs[0].id, delta=-1)

    assert _ids(manager) == [jobs[0].id, jobs[1].id]


def test_move_job_skips_non_queued_neighbors(manager: PrintJobManager) -> None:
    """Reordering only ever affects relative order among QUEUED jobs —
    swapping past an already-PRINTING or finished job wouldn't change
    what the worker does next, only produce a confusing list order."""
    printing = _make_job(status=JobStatus.PRINTING)
    queued_a = _make_job()
    queued_b = _make_job()
    for job in (printing, queued_a, queued_b):
        manager.enqueue(job, width_px=100, chunk_height_px=100)

    manager.move_job(queued_b.id, delta=-1)

    assert _ids(manager) == [printing.id, queued_b.id, queued_a.id]


def test_move_job_not_queued_is_a_no_op(manager: PrintJobManager) -> None:
    done = _make_job(status=JobStatus.DONE)
    queued = _make_job()
    for job in (done, queued):
        manager.enqueue(job, width_px=100, chunk_height_px=100)

    manager.move_job(done.id, delta=1)

    assert _ids(manager) == [done.id, queued.id]


def test_move_job_unknown_id_is_a_no_op(manager: PrintJobManager) -> None:
    job = _make_job()
    manager.enqueue(job, width_px=100, chunk_height_px=100)

    manager.move_job("does-not-exist", delta=1)  # must not raise

    assert _ids(manager) == [job.id]


def test_clear_queue_cancels_paused_error_jobs(manager: PrintJobManager) -> None:
    """Bug report: "Очистить ничего не делает" whenever the queue held an
    errored job — clear_queue() used to leave PAUSED_ERROR alone entirely,
    which looked exactly like the button doing nothing whenever that was
    the only thing left in the queue."""
    paused = _make_job(status=JobStatus.PAUSED_ERROR)
    manager.enqueue(paused, width_px=100, chunk_height_px=100)

    manager.clear_queue()

    assert manager.list_jobs() == []


def test_clear_queue_still_leaves_actively_printing_jobs_alone(
    manager: PrintJobManager,
) -> None:
    printing = _make_job(status=JobStatus.PRINTING)
    manager.enqueue(printing, width_px=100, chunk_height_px=100)

    manager.clear_queue()

    assert _ids(manager) == [printing.id]
    assert printing.status == JobStatus.PRINTING
