from paperi.models.enums import PrinterModel
from paperi.models.printer_specs import NATIVE_WIDTH_PX, mm_to_px, safe_content_width_px


def test_a40_safe_width_is_narrower_than_native() -> None:
    # Verified live against real hardware (Stage 4 HCI trace) — see
    # docs/hardware-notes.md. The rightmost ~64px of this A40 unit isn't
    # reliably printed.
    assert safe_content_width_px(PrinterModel.A40) == 1664
    assert NATIVE_WIDTH_PX[PrinterModel.A40] == 1728


def test_unverified_models_default_to_native_width() -> None:
    for model in (PrinterModel.A6, PrinterModel.A6_PLUS, PrinterModel.A40_PLUS):
        assert safe_content_width_px(model) == NATIVE_WIDTH_PX[model]


def test_mm_to_px_matches_203_dpi() -> None:
    # 25.4mm == 1 inch == 203px at the printer's real 203dpi (docs/stage5-
    # ux-plan.md M5.5 — same physical dot pitch as pdf_renderer.py's own
    # _RENDER_DPI).
    assert mm_to_px(25.4) == 203


def test_mm_to_px_rounds_and_floors_at_one_pixel() -> None:
    assert mm_to_px(0) == 1  # never zero/negative — a 0px image is invalid
    assert mm_to_px(-5) == 1
