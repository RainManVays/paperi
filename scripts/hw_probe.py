#!/usr/bin/env python3
"""
Stage 0 hardware probe for a real Peripage printer.

Not packaged with the app — throwaway script to confirm connectivity and
empirically measure a safe chunk_height_px before Stage 1+ bakes in
defaults. Run inside the .venv-bt environment (see docs/BLUETOOTH_SETUP.md).

Usage:
    python scripts/hw_probe.py info      <MAC>
    python scripts/hw_probe.py text       <MAC> [--text "hello"]
    python scripts/hw_probe.py chunk-test <MAC> [--chunk-height 220] [--pause 2.0] [--chunks 3]
"""

import argparse
import os
import sys
import time
from pathlib import Path

import peripage
from PIL import Image, ImageDraw, ImageFont

# Same font/size as infra/renderers/text_renderer.py — kept as a literal
# duplicate here (not imported from periprint) since this script
# deliberately stays dependency-free from the main package and runs in a
# separate venv (.venv-bt).
_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
)
_FONT_SIZE_PX = 24


def _load_monospace_font() -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, _FONT_SIZE_PX)
    return ImageFont.load_default(_FONT_SIZE_PX)


def connect(mac: str) -> peripage.Printer:
    printer = peripage.Printer(mac, peripage.PrinterType.A40)
    printer.connect()

    # WORKAROUND (verified on this machine's python3-bluez 0.23-5.1build3 /
    # BlueZ 5.72): PyBluez's own BluetoothSocket.send()/.recv() raise
    # OSError(14, "Bad address") on this build even though the RFCOMM
    # connection itself is fine (confirmed: os.write/os.read on the raw fd
    # work). Bypass PyBluez's C-level send/recv and talk to the fd directly.
    # settimeout() below also puts the fd in non-blocking mode, so a plain
    # os.read() would raise BlockingIOError without the set_blocking(True).
    fd = printer.sock.fileno()
    os.set_blocking(fd, True)
    printer.sock.send = lambda data: os.write(fd, data)
    printer.sock.recv = lambda n: os.read(fd, n)

    printer.reset()
    return printer


def cmd_info(args: argparse.Namespace) -> None:
    printer = connect(args.mac)
    try:
        print("connected:", printer.isConnected())
        print("row_width (native_width_px):", printer.getRowWidth())
        print("row_bytes:", printer.getRowBytes())
        print("row_characters:", printer.getRowCharacters())
        print("device name:", printer.getDeviceName())
        print("firmware:", printer.getDeviceFirmware())
        print("battery %:", printer.getDeviceBattery())
    finally:
        printer.disconnect()


def cmd_text(args: argparse.Namespace) -> None:
    printer = connect(args.mac)
    try:
        printer.setConcentration(args.concentration, wait=True)
        printer.printlnASCII(args.text)
        printer.printBreak(60)
    finally:
        printer.disconnect()


def _striped_test_image(width: int, height: int) -> Image.Image:
    """A test image with a mix of light/dark bands, to exercise the
    'adaptive pause on dark chunks' heuristic, not just a blank/light image."""
    img = Image.new("L", (width, height), color=255)
    draw = ImageDraw.Draw(img)
    band = height // 6 or 1
    for i in range(0, height, band * 2):
        draw.rectangle([0, i, width, min(i + band, height)], fill=0)
    draw.text((10, 10), "PeriPrint hw_probe chunk test", fill=0)
    return img


# Deliberately real prose, not solid bars: on a binary 1-bit thermal head a
# solid black square looks equally black regardless of heat, but a heat
# difference is far more likely to show up as stroke thickness/bleed/
# faintness on fine text — which is also what real documents actually are.
# One English + one Cyrillic line (RFC and most target documents are
# Russian) for representative character coverage.
_HEAT_TEST_LINES = (
    "The quick brown fox jumps over the lazy dog 0123456789",
    "Съешь ещё этих мягких французских булок, да выпей чаю",
)


def _heat_test_chunk(width: int, label: str) -> Image.Image:
    font = _load_monospace_font()
    line_height = _FONT_SIZE_PX + 6
    margin = 12
    height = margin * 2 + line_height * (1 + len(_HEAT_TEST_LINES))
    img = Image.new("L", (width, height), color=255)
    draw = ImageDraw.Draw(img)
    y = margin
    draw.text((margin, y), label, fill=0, font=font)
    y += line_height
    for line in _HEAT_TEST_LINES:
        draw.text((margin, y), line, fill=0, font=font)
        y += line_height
    return img


def cmd_heat_test(args: argparse.Namespace) -> None:
    """docs/stage5-ux-plan.md §0.3: is opcode 10ff81 (methods j()/v() in
    the decompiled app) a real quality knob, unlike concentration
    (confirmed no visible effect at 2/3/4 on this A40)? Result: also no
    visible effect (20-120 tested) — and re-decompiling afterward found
    this opcode's only real call sites are about paper positioning for
    label printing, not print density/heat, which may just explain why.
    See docs/bluetooth-protocol-trace-analysis.md §7.5. Kept for
    reference/reproducibility, not because this is still an open
    question. Prints one labeled group per --values entry, back-to-back,
    for physical side-by-side comparison of text legibility/stroke
    weight/bleed. Values are clamped to 0-120 — the decompiled app's own
    ceiling for "new" chipsets like the A40 (see
    PeripageClient.MAX_PRINT_HEAT) — this script does not attempt to probe
    past what the manufacturer's own app sends to this printer class."""
    values = [max(0, min(120, int(v))) for v in args.values.split(",")]
    printer = connect(args.mac)
    try:
        printer.setConcentration(args.concentration, wait=True)
        width = printer.getRowWidth()
        for i, value in enumerate(values):
            print(f"group {i + 1}/{len(values)}: heat={value}")
            printer.tellPrinter(bytes.fromhex("10ff81") + bytes([value]))
            chunk = _heat_test_chunk(width, f"HEAT={value}")
            printer.printImage(chunk, delay=args.delay)
            if i < len(values) - 1:
                print(f"pausing {args.pause}s to cool down...")
                time.sleep(args.pause)
        printer.printBreak(60)
        print("done — compare groups for visible darkness/contrast/bleed differences.")
    finally:
        printer.disconnect()


def cmd_chunk_test(args: argparse.Namespace) -> None:
    printer = connect(args.mac)
    try:
        printer.setConcentration(args.concentration, wait=True)
        width = printer.getRowWidth()
        for i in range(args.chunks):
            print(f"printing chunk {i + 1}/{args.chunks} (height={args.chunk_height}px)...")
            chunk = _striped_test_image(width, args.chunk_height)
            printer.printImage(chunk, delay=args.delay)
            if i < args.chunks - 1:
                print(f"pausing {args.pause}s to cool down...")
                time.sleep(args.pause)
        printer.printBreak(60)
        print("done — inspect the printout for stalls/skips/uneven darkness.")
    finally:
        printer.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_info = sub.add_parser("info", help="Connect, print device info, disconnect. No paper used.")
    p_info.add_argument("mac")
    p_info.set_defaults(func=cmd_info)

    p_text = sub.add_parser("text", help="Print one short ASCII line. Uses paper.")
    p_text.add_argument("mac")
    p_text.add_argument("--text", default="PeriPrint hw_probe: hello from Stage 0")
    p_text.add_argument("--concentration", type=int, default=2, choices=[0, 1, 2])
    p_text.set_defaults(func=cmd_text)

    p_chunk = sub.add_parser(
        "chunk-test", help="Print N striped chunks with a pause between them. Uses paper."
    )
    p_chunk.add_argument("mac")
    p_chunk.add_argument("--chunk-height", type=int, default=220)
    p_chunk.add_argument("--pause", type=float, default=2.0)
    p_chunk.add_argument("--chunks", type=int, default=3)
    # Defaults per docs/hardware-notes.md empirical findings on the real
    # ALD-Y200/A40 unit: concentration=2, delay=0.05 gave the best density.
    p_chunk.add_argument("--concentration", type=int, default=2, choices=[0, 1, 2])
    p_chunk.add_argument("--delay", type=float, default=0.05)
    p_chunk.set_defaults(func=cmd_chunk_test)

    p_heat = sub.add_parser(
        "heat-test",
        help="Print one labeled group per heat value, back-to-back. Uses paper.",
    )
    p_heat.add_argument("mac")
    p_heat.add_argument(
        "--values", default="20,40,60,80,100,120", help="comma-separated, each 0-120"
    )
    p_heat.add_argument("--pause", type=float, default=2.0)
    p_heat.add_argument("--concentration", type=int, default=2, choices=[0, 1, 2])
    p_heat.add_argument("--delay", type=float, default=0.001)
    p_heat.set_defaults(func=cmd_heat_test)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
