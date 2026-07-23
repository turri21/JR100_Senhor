#!/usr/bin/env python3
# ============================================================================
#
#  JR100_MiSTer: extract a raw 8 KiB ROM image (boot.rom) from a
#  JR-100 PROG container.
#
#  Parsing is delegated to pyjr100emu's BasicRom so the extracted bytes
#  are exactly what the reference emulator maps at E000-FFFF (char ROM
#  first 1 KiB, BASIC from offset 0400). The output is what the MiSTer
#  core's loader expects as /media/fat/games/JR100/boot.rom.
#
#  Copyright (C) 2026 Zabaglione
#  SPDX-License-Identifier: GPL-2.0-or-later
#
# ============================================================================
"""Extract a raw 8 KiB boot.rom from a JR-100 PROG container."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EMU = Path(os.environ.get("JR100EMU_PATH", REPO.parent / "jr100emu"))
sys.path.insert(0, str(EMU / "src"))

from jr100emu.jr100.memory import BasicRom  # noqa: E402

ROM_START = 0xE000
ROM_LENGTH = 0x2000


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prog", help="input PROG container (e.g. jr100rom.prg)")
    parser.add_argument("out", help="output raw image (e.g. boot.rom)")
    args = parser.parse_args()

    source = Path(args.prog)
    if not source.is_file():
        print(f"error: {source} not found", file=sys.stderr)
        return 2
    with source.open("rb") as stream:
        if stream.read(4) != BasicRom.PROG_FILE_ID:
            print(f"error: {source} is not a PROG container", file=sys.stderr)
            return 2

    rom = BasicRom(str(source), ROM_START, ROM_LENGTH)
    data = bytes(value & 0xFF for value in rom.data)
    if len(data) != ROM_LENGTH:
        print(f"error: unexpected ROM length {len(data)}", file=sys.stderr)
        return 2
    if not any(data):
        print("error: extracted image is empty (bad container?)", file=sys.stderr)
        return 2

    Path(args.out).write_bytes(data)
    print(f"wrote {args.out}: {ROM_LENGTH} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
