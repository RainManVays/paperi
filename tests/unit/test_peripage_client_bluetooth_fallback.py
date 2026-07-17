import builtins

import pytest

from periprint.infra.peripage_client import PeripageConnectionError, _default_printer_factory
from periprint.models.enums import PrinterModel


def test_default_printer_factory_missing_bluetooth_module_raises_friendly_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_import = builtins.__import__

    def _fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "peripage":
            raise ImportError("No module named 'bluetooth'")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", _fake_import)

    with pytest.raises(PeripageConnectionError, match="sudo apt install python3-bluez"):
        _default_printer_factory("28:D4:1E:01:34:C4", PrinterModel.A40)
