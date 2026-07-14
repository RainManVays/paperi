from collections.abc import Callable

import customtkinter as ctk


class QueuePanel(ctk.CTkFrame):
    def __init__(
        self,
        master: ctk.CTkBaseClass,
        on_select_file: Callable[[], None] | None = None,
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

        self.print_all_button = ctk.CTkButton(button_row, text="Печать всё")
        self.print_all_button.pack(side="left", padx=(0, 8))

        self.clear_button = ctk.CTkButton(button_row, text="Очистить")
        self.clear_button.pack(side="left")
