import customtkinter as ctk

from periprint.infra.config_store import ConfigStore
from periprint.services.printer_manager import PrinterManager
from periprint.ui.main_window import MainWindow


def main() -> None:
    config = ConfigStore().load()
    ctk.set_appearance_mode(config.theme)

    printer_manager = PrinterManager()
    window = MainWindow(printer_manager=printer_manager)
    window.mainloop()


if __name__ == "__main__":
    main()
