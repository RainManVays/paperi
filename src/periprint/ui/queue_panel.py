from collections.abc import Callable
from pathlib import Path

import customtkinter as ctk
from tkinterdnd2 import DND_FILES

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
        on_files_dropped: Callable[[list[str]], None] | None = None,
        on_print_all: Callable[[], None] | None = None,
        on_clear: Callable[[], None] | None = None,
        on_move_job: Callable[[str, int], None] | None = None,
        **kwargs,
    ):
        super().__init__(master, **kwargs)
        self._on_move_job = on_move_job
        self._row_widgets: list[ctk.CTkFrame] = []

        title = ctk.CTkLabel(self, text="ОЧЕРЕДЬ ПЕЧАТИ", font=ctk.CTkFont(weight="bold"))
        title.pack(anchor="w", padx=8, pady=(8, 0))

        # A scrollable frame of per-job rows (not the previous read-only
        # CTkTextbox) — needed so each QUEUED job can carry its own
        # move-up/move-down buttons (Stage 5 M5.4 reorder).
        self.queue_list = ctk.CTkScrollableFrame(self, height=150)
        self.queue_list.pack(fill="both", expand=True, padx=8, pady=8)

        self._empty_label = ctk.CTkLabel(self.queue_list, text="(очередь пуста)")
        self._empty_label.pack(anchor="w")

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
        if on_files_dropped is not None:
            self.dropzone.drop_target_register(DND_FILES)
            self.dropzone.dnd_bind(
                "<<Drop>>",
                lambda event: on_files_dropped(list(self.dropzone.tk.splitlist(event.data))),
            )

        button_row = ctk.CTkFrame(self, fg_color="transparent")
        button_row.pack(fill="x", padx=8, pady=(0, 8))

        self.print_all_button = ctk.CTkButton(button_row, text="Печать всё", command=on_print_all)
        self.print_all_button.pack(side="left", padx=(0, 8))

        self.clear_button = ctk.CTkButton(button_row, text="Очистить", command=on_clear)
        self.clear_button.pack(side="left")

    def set_jobs(self, jobs: list[PrintJob]) -> None:
        for row in self._row_widgets:
            row.destroy()
        self._row_widgets = []

        if not jobs:
            self._empty_label.pack(anchor="w")
            return
        self._empty_label.pack_forget()

        for job in jobs:
            row = ctk.CTkFrame(self.queue_list, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=_format_job_line(job), anchor="w").pack(
                side="left", fill="x", expand=True
            )
            # Only QUEUED jobs are meaningfully reorderable — see
            # PrintJobManager.move_job()'s own docstring for why swapping
            # past an already-started/finished job wouldn't do anything.
            if self._on_move_job is not None and job.status == JobStatus.QUEUED:
                ctk.CTkButton(
                    row,
                    text="▲",
                    width=28,
                    command=lambda job_id=job.id: self._on_move_job(job_id, -1),
                ).pack(side="left", padx=(4, 0))
                ctk.CTkButton(
                    row,
                    text="▼",
                    width=28,
                    command=lambda job_id=job.id: self._on_move_job(job_id, 1),
                ).pack(side="left", padx=(4, 0))
            self._row_widgets.append(row)
