from pathlib import Path

import customtkinter as ctk

from periprint.infra.history_store import HistoryEntry

# HistoryEntry.status is JobStatus.value (a plain string, see
# job_manager.py's HistoryEntry.record() calls) — only the three terminal
# statuses ever land here, since PrintJobManager only records finished jobs.
_STATUS_LABELS = {
    "done": "готово",
    "failed": "не удалось",
    "cancelled": "отменено",
}


def _format_history_line(entry: HistoryEntry) -> str:
    name = Path(entry.source_path).name
    status = _STATUS_LABELS.get(entry.status, entry.status)
    line = f"{name} — {status}"
    if entry.finished_at is not None:
        line = f"{line} ({entry.finished_at.strftime('%d.%m %H:%M')})"
    if entry.status == "failed" and entry.error_message:
        line = f"{line}: {entry.error_message}"
    return line


class HistoryPanel(ctk.CTkFrame):
    """Read-only list of finished print jobs (docs/stage5-ux-plan.md point
    13, option C — a separate tab so the active queue never has to mix
    "still needs printing" with "already printed", matching how Windows
    Print Spooler/CUPS/Android's print spooler all keep a finished job's
    history apart from the active queue view)."""

    def __init__(self, master: ctk.CTkBaseClass, **kwargs):
        super().__init__(master, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        title = ctk.CTkLabel(self, text="ИСТОРИЯ ПЕЧАТИ", font=ctk.CTkFont(weight="bold"))
        title.grid(row=0, column=0, sticky="w", padx=8, pady=(8, 0))

        self.entries_list = ctk.CTkScrollableFrame(self)
        self.entries_list.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)

        self._empty_label = ctk.CTkLabel(self.entries_list, text="(история пуста)")
        self._empty_label.pack(anchor="w")
        self._row_widgets: list[ctk.CTkLabel] = []

    def set_entries(self, entries: list[HistoryEntry]) -> None:
        for row in self._row_widgets:
            row.destroy()
        self._row_widgets = []

        if not entries:
            self._empty_label.pack(anchor="w")
            return
        self._empty_label.pack_forget()

        for entry in entries:
            label = ctk.CTkLabel(
                self.entries_list, text=_format_history_line(entry), anchor="w", justify="left"
            )
            label.pack(fill="x", pady=2)
            # Same wraplength-via-<Configure> pattern as queue_panel.py's
            # rows — a long error message needs to wrap, not run off the
            # scrollable frame's edge.
            label.bind(
                "<Configure>", lambda event, widget=label: widget.configure(wraplength=event.width)
            )
            self._row_widgets.append(label)
