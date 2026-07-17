import customtkinter as ctk

from paperi.infra.config_store import ConfigStore
from paperi.services.printer_manager import PrinterManager
from paperi.ui.main_window import MainWindow


def main() -> None:
    config = ConfigStore().load()
    ctk.set_appearance_mode(config.theme)

    printer_manager = PrinterManager()
    window = MainWindow(printer_manager=printer_manager)
    window.mainloop()


if __name__ == "__main__":
    main()
