from datetime import datetime

from paperi.models.enums import PrinterModel
from paperi.models.printer_profile import PrinterProfile


def test_round_trip_without_last_connected_at() -> None:
    profile = PrinterProfile(
        id="abc-123",
        name="Мой A40",
        mac="28:D4:1E:01:34:C4",
        model=PrinterModel.A40,
    )

    restored = PrinterProfile.from_dict(profile.to_dict())

    assert restored == profile


def test_round_trip_with_last_connected_at() -> None:
    profile = PrinterProfile(
        id="abc-123",
        name="Мой A40",
        mac="28:D4:1E:01:34:C4",
        model=PrinterModel.A40,
        default_concentration=2,
        default_break=90,
        chunk_height_px=150,
        last_connected_at=datetime(2026, 7, 14, 12, 0, 0),
    )

    restored = PrinterProfile.from_dict(profile.to_dict())

    assert restored == profile


def test_defaults() -> None:
    profile = PrinterProfile(id="x", name="Test", mac="00:00:00:00:00:00", model=PrinterModel.A6)

    assert profile.default_concentration == 1
    assert profile.default_break == 60
    assert profile.chunk_height_px == 220
    assert profile.last_connected_at is None
