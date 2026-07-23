#!/usr/bin/env python3
# ============================================================================
#
#  JR100_MiSTer: convert JR-100 BASIC text (.bas) to a PROG v2 container
#  with a PBAS section, loadable from the OSD "Load PRG" slot.
#
#  The text is encoded by pyjr100emu's load_basic_text (line numbers,
#  \xx escapes, per-line terminators), so the resulting bytes are
#  exactly what the reference emulator would place at 0246; the core's
#  RTL loader then performs the same workspace finalisation.
#
#  Copyright (C) 2026 Zabaglione
#  SPDX-License-Identifier: GPL-2.0-or-later
#
# ============================================================================
"""Convert JR-100 BASIC text to a PROG v2 (PBAS) container."""

from __future__ import annotations

import argparse
import os
import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EMU = Path(os.environ.get("JR100EMU_PATH", REPO.parent / "jr100emu"))
sys.path.insert(0, str(EMU / "src"))

from jr100emu.emulator.file.program import load_basic_text  # noqa: E402


class _RecordingMemory:
    """MemorySystem stand-in that records byte writes."""

    def __init__(self) -> None:
        self.data: dict[int, int] = {}

    def store8(self, address: int, value: int) -> None:
        self.data[address & 0xFFFF] = value & 0xFF

    def store16(self, address: int, value: int) -> None:
        self.store8(address, (value >> 8) & 0xFF)
        self.store8(address + 1, value & 0xFF)

    def load8(self, address: int) -> int:
        return self.data.get(address & 0xFFFF, 0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bas", help="input BASIC text file")
    parser.add_argument("out", help="output .prg (PROG v2) file")
    args = parser.parse_args()

    memory = _RecordingMemory()
    info = load_basic_text(memory, args.bas)
    region = info.address_regions[0]
    payload = bytes(memory.data.get(a, 0) for a in range(region.start, region.end + 1))

    name = Path(args.bas).stem.upper().encode("utf-8")[:255]
    pnam = struct.pack("<I", len(name)) + name
    pbas = struct.pack("<I", len(payload)) + payload
    container = (
        b"PROG" + struct.pack("<I", 2)
        + struct.pack("<II", 0x4D414E50, len(pnam)) + pnam   # PNAM
        + struct.pack("<II", 0x53414250, len(pbas)) + pbas   # PBAS
    )
    Path(args.out).write_bytes(container)
    print(f"wrote {args.out}: {len(container)} bytes (BASIC {len(payload)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
