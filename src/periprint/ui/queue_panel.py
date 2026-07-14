from collections.abc import Callable
from pathlib import Path

import customtkinter as ctk

from periprint.models.enums import JobStatus
from periprint.models.job import PrintJob

_STATUS_LABELS = {
    JobStatus.QUEUED: "в очереди",
    JobStatus.RENDERING: "рендеринг...",
    JobStatus.PRINTING: "печать",
    JobStatus.PAUSED_ERROR: "ошибка — приостановлено",
    JobStatus.DONE: "готово",
    JobStatus.FAILED: "не удалось",
    JobStatus.CANCELLED: "отменено",
}


def _format_job_line(job: PrintJob) -> str:
    name = Path(job.document.source_path).name
    status = _STATUS_LABELS[job.status]
    if job.status == JobStatus.PRINTING and job.total_chunks:
        percent = round(100 * job.completed_chunks / job.total_chunks)
        status = f"{status} {job.completed_chunks}/{job.total_chunks} ({percent}%)"
    elif job.status == JobStatus.PAUSED_ERROR and job.error_message:
        status = f"{status}: {job.error_message}"
    return f"{name} — {status}"


class QueuePanel(ctk.CTkFrame):
    def __init__(
        self,
        master: ctk.CTkBaseClass,
        on_select_file: Callable[[], None] | None = None,
        on_print_all: Callable[[], None] | None = None,
        on_clear: Callable[[], None] | None = None,
        **kwargs,
    ):
        super().__init__(master, **kwargs)

        title = ctk.CTkLabel(self, text="ОЧЕРЕДЬ ПЕЧАТИ", font=ctk.CTkFont(weight="bold"))
        title.pack(anchor="w", padx=8, pady=(8, 0))

        self.queue_list = ctk.CTkTextbox(self, height=150)
        self.queue_list.insert("1.0", "(очередь пуста)")
        self.queue_list.configure(state="disabled")
        self.queue_list.pack(fill="both", expand=True, padx=8, pady=8)

        self.dropzone = ctk.CTkLabel(
            self,
            text="Перетащите файлы сюда\nили нажмите для выбора",
            height=80,
            fg_color=("gray85", "gray20"),
            corner_radius=8,
            cursor="hand2",
        )
        self.dropzone.pack(fill="x", padx=8, pady=8)
        if on_select_file is not None:
            self.dropzone.bind("<Button-1>", lambda _event: on_select_file())

        button_row = ctk.CTkFrame(self, fg_color="transparent")
        button_row.pack(fill="x", padx=8, pady=(0, 8))

        self.print_all_button = ctk.CTkButton(button_row, text="Печать всё", command=on_print_all)
        self.print_all_button.pack(side="left", padx=(0, 8))

        self.clear_button = ctk.CTkButton(button_row, text="Очистить", command=on_clear)
        self.clear_button.pack(side="left")

    def set_jobs(self, jobs: list[PrintJob]) -> None:
        self.queue_list.configure(state="normal")
        self.queue_list.delete("1.0", "end")
        if not jobs:
            self.queue_list.insert("1.0", "(очередь пуста)")
        else:
            self.queue_list.insert("1.0", "\n".join(_format_job_line(job) for job in jobs))
        self.queue_list.configure(state="disabled")
