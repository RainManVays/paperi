from periprint.models.enums import PrinterModel
from periprint.models.printer_specs import NATIVE_WIDTH_PX, safe_content_width_px


def test_a40_safe_width_is_narrower_than_native() -> None:
    # Verified live against real hardware (Stage 4 HCI trace) — see
    # docs/hardware-notes.md. The rightmost ~64px of this A40 unit isn't
    # reliably printed.
    assert safe_content_width_px(PrinterModel.A40) == 1664
    assert NATIVE_WIDTH_PX[PrinterModel.A40] == 1728


def test_unverified_models_default_to_native_width() -> None:
    for model in (PrinterModel.A6, PrinterModel.A6_PLUS, PrinterModel.A40_PLUS):
        assert safe_content_width_px(model) == NATIVE_WIDTH_PX[model]
