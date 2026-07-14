import customtkinter as ctk

from periprint.services.printer_manager import PrinterManager
from periprint.ui.preview_panel import PreviewPanel
from periprint.ui.printer_panel import PrinterPanel
from periprint.ui.queue_panel import QueuePanel
from periprint.ui.settings_dialog import SettingsDialog


class MainWindow(ctk.CTk):
    def __init__(self, printer_manager: PrinterManager | None = None) -> None:
        super().__init__()
        self.title("PeriPrint")
        self.geometry("900x600")

        self._printer_manager = printer_manager or PrinterManager()
        self._settings_dialog: SettingsDialog | None = None

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.printer_panel = PrinterPanel(self, on_open_settings=self._open_settings)
        self.printer_panel.grid(row=0, column=0, sticky="ew")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self.queue_panel = QueuePanel(body)
        self.queue_panel.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=8)

        self.preview_panel = PreviewPanel(body)
        self.preview_panel.grid(row=0, column=1, sticky="nsew", padx=(4, 8), pady=8)

        self.status_bar = ctk.CTkLabel(self, text="Статус: готово", anchor="w")
        self.status_bar.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 8))

    def _open_settings(self) -> None:
        if self._settings_dialog is None or not self._settings_dialog.winfo_exists():
            self._settings_dialog = SettingsDialog(self, self._printer_manager)
        else:
            self._settings_dialog.focus()
