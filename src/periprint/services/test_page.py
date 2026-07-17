"""Generates a synthetic diagnostic image (services/test_page.py) printed via
the normal DocumentPipeline/PrintJobManager path (see
ui/main_window.py::_handle_print_test_page) — a "Печать тестовой страницы"
action in Settings, not a real user document. Content is chosen to expose
the specific hardware failure modes this project has actually hit or
documented, not a generic nozzle-check pattern:
  - a 0-100% density step wedge (relies on normalize_to_1bit's dithering to
    turn each flat gray level into a stipple pattern — the same mechanism a
    real dithered photo goes through, see infra/renderers/base.py),
  - a solid full-width black bar and a fine vertical comb, both meant to
    turn a dead/weak printhead element into an obvious continuous vertical
    gap rather than something only visible on close inspection,
  - a diagonal-in-a-square, meant to turn any horizontal stretch (see
    printer_specs.py's own warning that printImage() unconditionally
    resizes to the model's native row width) into a visibly bent line
    instead of a subtle few-percent size error,
  - an mm ruler at the real 203dpi dot pitch (printer_specs.PRINT_DPI), so
    the user can check the ruler against a real one instead of guessing.
Renders at content_width_px (the same safe width every real document
renders at, see printer_specs.SAFE_CONTENT_WIDTH_PX) rather than the full
native canvas width, so the test page prints through the exact same path a
real document would — it's a diagnostic of that path, not a probe of a
wider, normally-unused one.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont

from periprint.models.enums import PrinterModel
from periprint.models.printer_specs import PRINT_DPI
from periprint.utils.version import app_version

# Same candidates/fallback as infra/renderers/text_renderer.py — kept as a
# separate copy rather than importing that renderer-local constant, since
# the two have no other coupling and text_renderer's is private to it.
_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
)

_MARGIN_PX = 16
_SECTION_GAP_PX = 20
_RULE_THICKNESS_PX = 2
_TITLE_FONT_SIZE = 30
_BODY_FONT_SIZE = 20
_CAPTION_FONT_SIZE = 18
_LABEL_FONT_SIZE = 14
_STEP_COUNT = 11  # 0%, 10%, ..., 100%
_STEP_HEIGHT_PX = 70
_SOLID_BAR_HEIGHT_PX = 50
_VERTICAL_COMB_HEIGHT_PX = 70
_VERTICAL_COMB_PERIOD_PX = 4
_HORIZONTAL_COMB_HEIGHT_PX = 60
_HORIZONTAL_COMB_PERIOD_PX = 6
_CHECKERBOARD_CELL_PX = 8
_CHECKERBOARD_HEIGHT_PX = 80
_DIAGONAL_MAX_SIZE_PX = 300
_RULER_TICK_SHORT_PX = 10
_RULER_TICK_LONG_PX = 22
_PX_PER_MM = PRINT_DPI / 25.4
_CORNER_MARK_SIZE_PX = 16
_CORNER_MARK_MARGIN_PX = 4
# Generous upper bound the page is drawn into, then cropped to actual
# content height — real content lands well under 2000px (see module tests),
# this just avoids computing an exact height up front.
_MAX_CANVAS_HEIGHT_PX = 4000


def _load_font(size: int) -> PIL.ImageFont.ImageFont | PIL.ImageFont.FreeTypeFont:
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            return PIL.ImageFont.truetype(path, size)
    return PIL.ImageFont.load_default(size)


def _draw_rule(draw: PIL.ImageDraw.ImageDraw, y: int, width_px: int) -> int:
    y += _SECTION_GAP_PX // 2
    draw.line([(0, y), (width_px, y)], fill=0, width=_RULE_THICKNESS_PX)
    return y + _RULE_THICKNESS_PX + _SECTION_GAP_PX // 2


def _draw_caption(draw: PIL.ImageDraw.ImageDraw, y: int, text: str) -> int:
    draw.text((_MARGIN_PX, y), text, fill=0, font=_load_font(_CAPTION_FONT_SIZE))
    return y + _CAPTION_FONT_SIZE + 8


def _draw_header(
    draw: PIL.ImageDraw.ImageDraw,
    y: int,
    width_px: int,
    *,
    model: PrinterModel,
    canvas_width_px: int,
    profile_name: str,
    mac: str,
    concentration: int,
) -> int:
    draw.text(
        (_MARGIN_PX, y),
        "PERIPRINT — ТЕСТОВАЯ СТРАНИЦА",
        fill=0,
        font=_load_font(_TITLE_FONT_SIZE),
    )
    y += _TITLE_FONT_SIZE + 10

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"Дата/время: {timestamp}",
        f"Принтер: {profile_name}   MAC: {mac}",
        f"Модель: {model.value}   DPI: {PRINT_DPI}",
        f"Ширина печати: {width_px}px (полная ширина ленты: {canvas_width_px}px)",
        f"Концентрация: {concentration}   Версия приложения: {app_version()}",
    ]
    body_font = _load_font(_BODY_FONT_SIZE)
    for line in lines:
        draw.text((_MARGIN_PX, y), line, fill=0, font=body_font)
        y += _BODY_FONT_SIZE + 6
    return y


def _draw_density_steps(draw: PIL.ImageDraw.ImageDraw, y: int, width_px: int) -> int:
    y = _draw_caption(draw, y, "Градиент плотности (шаг 10%) — проверка настройки концентрации")
    label_font = _load_font(_LABEL_FONT_SIZE)
    usable_width = width_px - 2 * _MARGIN_PX
    step_width = usable_width // _STEP_COUNT
    for i in range(_STEP_COUNT):
        percent = i * 10
        gray = round(255 * (1 - percent / 100))
        x0 = _MARGIN_PX + i * step_width
        x1 = x0 + step_width - 2
        draw.rectangle([x0, y, x1, y + _STEP_HEIGHT_PX], fill=gray)
        draw.text((x0 + 2, y + _STEP_HEIGHT_PX + 4), str(percent), fill=0, font=label_font)
    return y + _STEP_HEIGHT_PX + _LABEL_FONT_SIZE + 10


def _draw_solid_bar(draw: PIL.ImageDraw.ImageDraw, y: int, width_px: int) -> int:
    y = _draw_caption(
        draw, y, "Сплошная заливка (100%) — разрыв полосы = неисправный элемент головки"
    )
    draw.rectangle([0, y, width_px - 1, y + _SOLID_BAR_HEIGHT_PX], fill=0)
    return y + _SOLID_BAR_HEIGHT_PX


def _draw_vertical_comb(draw: PIL.ImageDraw.ImageDraw, y: int, width_px: int) -> int:
    y = _draw_caption(draw, y, "Вертикальная гребёнка — пропуски = нерабочие элементы головки")
    for x in range(0, width_px, _VERTICAL_COMB_PERIOD_PX):
        draw.line([(x, y), (x, y + _VERTICAL_COMB_HEIGHT_PX)], fill=0, width=2)
    return y + _VERTICAL_COMB_HEIGHT_PX


def _draw_horizontal_comb(draw: PIL.ImageDraw.ImageDraw, y: int, width_px: int) -> int:
    y = _draw_caption(draw, y, "Горизонтальная гребёнка — проверка равномерности подачи бумаги")
    top = y
    row_y = top
    while row_y < top + _HORIZONTAL_COMB_HEIGHT_PX:
        draw.line([(0, row_y), (width_px, row_y)], fill=0, width=2)
        row_y += _HORIZONTAL_COMB_PERIOD_PX
    return top + _HORIZONTAL_COMB_HEIGHT_PX


def _draw_checkerboard(draw: PIL.ImageDraw.ImageDraw, y: int, width_px: int) -> int:
    y = _draw_caption(draw, y, "Шахматный узор — детализация и растекание точек")
    cell = _CHECKERBOARD_CELL_PX
    rows = _CHECKERBOARD_HEIGHT_PX // cell
    cols = width_px // cell
    for row in range(rows):
        for col in range(cols):
            if (row + col) % 2 == 0:
                x0, y0 = col * cell, y + row * cell
                draw.rectangle([x0, y0, x0 + cell - 1, y0 + cell - 1], fill=0)
    return y + rows * cell


def _draw_diagonal(draw: PIL.ImageDraw.ImageDraw, y: int, width_px: int) -> int:
    y = _draw_caption(
        draw, y, "Диагональ — линия должна остаться прямой (иначе растяжение по X)"
    )
    size = min(width_px - 2 * _MARGIN_PX, _DIAGONAL_MAX_SIZE_PX)
    x0 = (width_px - size) // 2
    draw.rectangle([x0, y, x0 + size, y + size], outline=0, width=2)
    draw.line([(x0, y), (x0 + size, y + size)], fill=0, width=2)
    draw.line([(x0 + size, y), (x0, y + size)], fill=0, width=2)
    return y + size


def _draw_ruler(draw: PIL.ImageDraw.ImageDraw, y: int, width_px: int) -> int:
    y = _draw_caption(
        draw, y, f"Линейка (мм при {PRINT_DPI} DPI) — сверьте расстояния с настоящей линейкой"
    )
    label_font = _load_font(_LABEL_FONT_SIZE)
    max_mm = int(width_px / _PX_PER_MM)
    for mm in range(0, max_mm + 1):
        x = round(mm * _PX_PER_MM)
        if x >= width_px:
            break
        is_major = mm % 10 == 0
        tick_height = _RULER_TICK_LONG_PX if is_major else _RULER_TICK_SHORT_PX
        draw.line([(x, y), (x, y + tick_height)], fill=0, width=2 if is_major else 1)
        if is_major:
            draw.text((x + 2, y + _RULER_TICK_LONG_PX + 2), str(mm), fill=0, font=label_font)
    return y + _RULER_TICK_LONG_PX + _LABEL_FONT_SIZE + 10


_TEXT_SAMPLE_LINES = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "abcdefghijklmnopqrstuvwxyz",
    "0123456789 !?.,:;-+=/()%",
    "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ",
    "абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
)


def _draw_text_sample(draw: PIL.ImageDraw.ImageDraw, y: int, width_px: int) -> int:
    y = _draw_caption(draw, y, "Образец текста — проверка чёткости символов")
    font = _load_font(_BODY_FONT_SIZE)
    for line in _TEXT_SAMPLE_LINES:
        draw.text((_MARGIN_PX, y), line, fill=0, font=font)
        y += _BODY_FONT_SIZE + 6
    return y


def _draw_footer(draw: PIL.ImageDraw.ImageDraw, y: int, width_px: int) -> int:
    return _draw_caption(draw, y, "Конец тестовой страницы")


def _draw_corner_crosshairs(draw: PIL.ImageDraw.ImageDraw, width_px: int, height_px: int) -> None:
    """Registration marks at all four corners of the finished page — a
    skewed/offset feed shows up as the crosshairs not lining up with the
    physical paper edges."""
    size = _CORNER_MARK_SIZE_PX
    margin = _CORNER_MARK_MARGIN_PX
    for cx, cy in (
        (margin, margin),
        (width_px - margin, margin),
        (margin, height_px - margin),
        (width_px - margin, height_px - margin),
    ):
        draw.line([(cx - size, cy), (cx + size, cy)], fill=0, width=2)
        draw.line([(cx, cy - size), (cx, cy + size)], fill=0, width=2)


_SECTIONS = (
    _draw_density_steps,
    _draw_solid_bar,
    _draw_vertical_comb,
    _draw_horizontal_comb,
    _draw_checkerboard,
    _draw_diagonal,
    _draw_ruler,
    _draw_text_sample,
)


def generate_test_page(
    *,
    model: PrinterModel,
    content_width_px: int,
    canvas_width_px: int,
    profile_name: str,
    mac: str,
    concentration: int,
) -> PIL.Image.Image:
    """Builds the full diagnostic page as a single "L"-mode image,
    content_width_px wide — the exact width a real document renders at for
    this printer (see ui/main_window.py::_resolve_render_target), so it
    goes through DocumentPipeline/PrintJobManager exactly like any other
    print job once handed to MainWindow._handle_print_test_page."""
    image = PIL.Image.new("L", (content_width_px, _MAX_CANVAS_HEIGHT_PX), color=255)
    draw = PIL.ImageDraw.Draw(image)

    y = _draw_header(
        draw,
        _MARGIN_PX,
        content_width_px,
        model=model,
        canvas_width_px=canvas_width_px,
        profile_name=profile_name,
        mac=mac,
        concentration=concentration,
    )
    for section in _SECTIONS:
        y = _draw_rule(draw, y, content_width_px)
        y = section(draw, y, content_width_px)
    y = _draw_rule(draw, y, content_width_px)
    y = _draw_footer(draw, y, content_width_px)
    y += _MARGIN_PX

    final = image.crop((0, 0, content_width_px, y))
    _draw_corner_crosshairs(PIL.ImageDraw.Draw(final), content_width_px, y)
    return final
