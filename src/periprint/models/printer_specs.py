from periprint.models.enums import PrinterModel

# Native print width per model, in pixels — matches peripage.PrinterType's
# hardcoded row_width constants (verified in Stage 0 against a real A40:
# native_width_px == 1728). Duplicated here (rather than importing peripage)
# so rendering/preview work without the optional `bluetooth` extra installed.
NATIVE_WIDTH_PX: dict[PrinterModel, int] = {
    PrinterModel.A6: 384,
    PrinterModel.A6_PLUS: 576,
    PrinterModel.A40: 1728,
    PrinterModel.A40_PLUS: 1848,
}
