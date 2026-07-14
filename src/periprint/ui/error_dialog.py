from collections.abc import Callable

import customtkinter as ctk


class ErrorDialog(ctk.CTkToplevel):
    """Spec §7.2: connection-drop mid-print. Offers reconnect (resume from
    the last successful chunk — PrintJobManager already tracks that via
    PrintJob.completed_chunks) or cancel."""

    def __init__(
        self,
        master: ctk.CTk,
        message: str,
        on_reconnect: Callable[[], None],
        on_cancel: Callable[[], None],
        **kwargs,
    ):
        super().__init__(master, **kwargs)
        self.title("Ошибка печати")
        self.geometry("380x160")
        self._on_reconnect = on_reconnect
        self._on_cancel = on_cancel

        ctk.CTkLabel(self, text=message, wraplength=340, justify="left").pack(
            padx=16, pady=16, fill="both", expand=True
        )

        button_row = ctk.CTkFrame(self, fg_color="transparent")
        button_row.pack(pady=(0, 16))

        ctk.CTkButton(button_row, text="Переподключиться", command=self._handle_reconnect).pack(
            side="left", padx=6
        )
        ctk.CTkButton(button_row, text="Отменить", command=self._handle_cancel).pack(
            side="left", padx=6
        )

    def _handle_reconnect(self) -> None:
        self.destroy()
        self._on_reconnect()

    def _handle_cancel(self) -> None:
        self.destroy()
        self._on_cancel()
