from periprint.models.enums import PrinterModel

# Native print width per model, in pixels — matches peripage.PrinterType's
# hardcoded row_width constants (verified in Stage 0 against a real A40:
# native_width_px == 1728). Duplicated here (rather than importing peripage)
# so rendering/preview work without the optional `bluetooth` extra installed.
# This is also the canvas width fed to printer.printImage() — it must stay
# exactly this value, since printImage() unconditionally resizes its input
# to PrinterType.<model>.spec.row_width, silently *stretching* (not padding)
# anything narrower.
NATIVE_WIDTH_PX: dict[PrinterModel, int] = {
    PrinterModel.A6: 384,
    PrinterModel.A6_PLUS: 576,
    PrinterModel.A40: 1728,
    PrinterModel.A40_PLUS: 1848,
}

# WORKAROUND, NOT A ROOT-CAUSE FIX — see TODO below and
# docs/hardware-notes.md "Known limitation" section before touching this.
#
# Empirically inferred (Stage 4) from a single byte in a real Bluetooth HCI
# snoop trace of the official Peripage Android app printing to this exact
# A40 unit: the app's (undocumented, unimplemented-by-us) protocol opcode
# `0x1f` carries a field that reads as row_bytes=208 (1664px), not the
# peripage library's assumed 216 (1728px) for this model. Reducing our
# content width to 1664px empirically fixed clipped text at the right edge.
#
# TODO: this is a patch applied *within the old, possibly-wrong protocol*
# (peripage's `0x1d763000` opcode), not a fix to the actual root cause. The
# official app does not use that opcode at all — it uses a different,
# entirely unreverse-engineered `0x1f...` protocol. We have not confirmed
# *why* 1664px is the right number (only that one trace byte suggested it),
# whether it holds for other A40 units/firmware revisions, or whether
# implementing the real `0x1f` protocol would remove the need for this
# entirely. Only verified for A40 — other models keep their full native
# width until similarly checked against real hardware.
SAFE_CONTENT_WIDTH_PX: dict[PrinterModel, int] = {
    PrinterModel.A40: 1664,
}


def safe_content_width_px(model: PrinterModel) -> int:
    return SAFE_CONTENT_WIDTH_PX.get(model, NATIVE_WIDTH_PX[model])
