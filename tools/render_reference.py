#!/usr/bin/env python3
# ============================================================================
#
#  JR100_MiSTer: render the reference frame with pyjr100emu's display model.
#
#  Inputs: the initial 64 KiB memory image (character ROM source) and a
#  final hex dump containing C000:C3FF (CGRAM + VRAM). Output is a P5
#  PGM (256x192) directly comparable with the Verilator harness --frame.
#
#  Note: pyjr100emu's user-defined plane only maps the 32 CGRAM glyphs
#  (codes 0x80-0x9F); the shared-VRAM glyphs (0xA0-0xFF) are a known
#  reference gap (AGENTS.md §7), so screens using them will differ from
#  the RTL, which implements the real-hardware behaviour.
#
#  Copyright (C) 2026 Zabaglione
#  SPDX-License-Identifier: GPL-2.0-or-later
#
# ============================================================================
"""Render a reference JR-100 frame from image + dump via pyjr100emu."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import trace_diff  # noqa: E402

EMU = Path(os.environ.get("JR100EMU_PATH", REPO.parent / "jr100emu"))
sys.path.insert(0, str(EMU / "src"))
from jr100emu.jr100.display import JR100Display  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, help="initial 64 KiB memory image")
    parser.add_argument("--dump", required=True, help="hex dump containing C000:C3FF")
    parser.add_argument("--font", choices=("normal", "user"), default="normal")
    parser.add_argument("--out", required=True, help="output PGM path")
    args = parser.parse_args()

    image = Path(args.image).read_bytes()
    if len(image) != 0x10000:
        print("error: image must be 65536 bytes", file=sys.stderr)
        return 2
    mem = trace_diff.parse_hex_dump(Path(args.dump).read_text(encoding="utf-8").splitlines())

    display = JR100Display()
    display.load_character_rom(list(image[0xE000:0xE800]))
    cgram = [mem.get(0xC000 + i, 0) for i in range(0x100)]
    display.load_user_defined_ram(cgram + [0] * (1024 - 256))
    display.set_video_ram([mem.get(0xC100 + i, 0) for i in range(768)])
    display.set_current_font(
        display.FONT_USER_DEFINED if args.font == "user" else display.FONT_NORMAL
    )

    pixels = display.render_pixels()
    with open(args.out, "wb") as fp:
        fp.write(b"P5\n256 192\n255\n")
        for row in pixels:
            fp.write(bytes(255 if value == 0xFFFFFF else 0 for value in row))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
