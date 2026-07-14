from pathlib import Path

from periprint.models.enums import PrinterModel
from periprint.services.printer_manager import PrinterManager


def test_add_profile_persists_across_instances(tmp_path: Path) -> None:
    path = tmp_path / "printers.json"

    manager = PrinterManager(path=path)
    profile = manager.add_profile(name="Мой A40", mac="28:D4:1E:01:34:C4", model=PrinterModel.A40)

    # Simulate an app restart: a fresh PrinterManager reading the same file.
    reloaded_manager = PrinterManager(path=path)

    assert reloaded_manager.list_profiles() == [profile]
    assert reloaded_manager.get_profile(profile.id) == profile


def test_list_profiles_empty_when_no_file(tmp_path: Path) -> None:
    manager = PrinterManager(path=tmp_path / "printers.json")

    assert manager.list_profiles() == []


def test_update_profile(tmp_path: Path) -> None:
    path = tmp_path / "printers.json"
    manager = PrinterManager(path=path)
    profile = manager.add_profile(name="Мой A40", mac="28:D4:1E:01:34:C4", model=PrinterModel.A40)

    profile.name = "Переименованный"
    manager.update_profile(profile)

    reloaded_manager = PrinterManager(path=path)
    assert reloaded_manager.get_profile(profile.id).name == "Переименованный"  # type: ignore[union-attr]


def test_remove_profile(tmp_path: Path) -> None:
    path = tmp_path / "printers.json"
    manager = PrinterManager(path=path)
    profile = manager.add_profile(name="Мой A40", mac="28:D4:1E:01:34:C4", model=PrinterModel.A40)

    manager.remove_profile(profile.id)

    reloaded_manager = PrinterManager(path=path)
    assert reloaded_manager.list_profiles() == []
