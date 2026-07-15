from collections.abc import Callable

import customtkinter as ctk
from tkinterdnd2 import DND_FILES


class EmptyStatePanel(ctk.CTkFrame):
    """periprint-spec.md §7.4: the "empty" state shown before any file is
    accepted — only big printer-connection icons and a drag&drop zone,
    no queue/preview/settings at all (those live in MainWindow's other
    widgets, simply not gridded while this panel is shown — see
    MainWindow._show_empty_state()/_show_expanded_state())."""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        on_open_settings: Callable[[], None] | None = None,
        on_connect_toggle: Callable[[], None] | None = None,
        on_find_printer: Callable[[], None] | None = None,
        on_select_file: Callable[[], None] | None = None,
        on_files_dropped: Callable[[list[str]], None] | None = None,
        **kwargs,
    ):
        super().__init__(master, **kwargs)
        self._on_connect_toggle = on_connect_toggle
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 0))
        ctk.CTkLabel(header, text="PeriPrint", font=ctk.CTkFont(size=16, weight="bold")).pack(
            side="left"
        )
        ctk.CTkButton(
            header, text="⚙", width=32, command=on_open_settings or (lambda: None)
        ).pack(side="right")

        icons_row = ctk.CTkFrame(self, fg_color="transparent")
        icons_row.grid(row=1, column=0, pady=(24, 24))

        # Big icon "button": emoji + connection status stacked in one
        # multi-line CTkButton — matches this codebase's existing emoji-
        # as-icon convention (queue_panel.py's per-kind glyphs) rather than
        # bundling separate icon image assets just for this.
        self.printer_button = ctk.CTkButton(
            icons_row,
            text="🖨️\nПринтер: не выбран",
            width=180,
            height=100,
            command=self._handle_connect_toggle,
        )
        self.printer_button.pack(side="left", padx=12)

        ctk.CTkButton(
            icons_row,
            text="🔍\nНайти принтер",
            width=180,
            height=100,
            command=on_find_printer or (lambda: None),
        ).pack(side="left", padx=12)

        self.dropzone = ctk.CTkLabel(
            self,
            text="Перетащите файлы сюда\nили нажмите для выбора",
            fg_color=("gray85", "gray20"),
            corner_radius=12,
            font=ctk.CTkFont(size=15),
        )
        self.dropzone.grid(row=2, column=0, sticky="nsew", padx=32, pady=(0, 32))
        if on_select_file is not None:
            self.dropzone.bind("<Button-1>", lambda _event: on_select_file())
        if on_files_dropped is not None:
            self.dropzone.drop_target_register(DND_FILES)
            self.dropzone.dnd_bind(
                "<<Drop>>",
                lambda event: on_files_dropped(list(self.dropzone.tk.splitlist(event.data))),
            )

    def _handle_connect_toggle(self) -> None:
        if self._on_connect_toggle:
            self._on_connect_toggle()

    def set_status(self, text: str) -> None:
        # printer_panel.set_status() gets the "Принтер: ..." text meant
        # for a single-line top bar; reused as-is here since it already
        # carries exactly the information this bigger button needs, just
        # wrapped onto its own line under the icon.
        self.printer_button.configure(text=f"🖨️\n{text}")

    def set_connect_button(self, *, text: str, enabled: bool) -> None:
        # No separate text label here (the button already shows the full
        # status via set_status()) — only enabled/disabled matters, same
        # semantics as PrinterPanel's dedicated connect button.
        del text
        self.printer_button.configure(state="normal" if enabled else "disabled")
