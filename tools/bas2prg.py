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
#  Hybrid BASIC + machine-language programs: each --bin ADDR:FILE adds
#  a PBIN section that loads FILE at hex address ADDR, e.g.
#      bas2prg.py game.bas game.prg --bin 1000:routine.bin
#  The BASIC side then reaches the code with USR($1000) etc.
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


def parse_bin_spec(spec: str) -> tuple[int, Path]:
    addr_text, _, file_text = spec.partition(":")
    if not file_text:
        raise argparse.ArgumentTypeError(f"--bin needs ADDR:FILE, got {spec!r}")
    try:
        addr = int(addr_text, 16)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"bad hex address in {spec!r}") from exc
    if not 0 <= addr <= 0xFFFF:
        raise argparse.ArgumentTypeError(f"address out of range in {spec!r}")
    return addr, Path(file_text)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bas", help="input BASIC text file")
    parser.add_argument("out", help="output .prg (PROG v2) file")
    parser.add_argument(
        "--bin", metavar="ADDR:FILE", type=parse_bin_spec, action="append",
        default=[],
        help="add a PBIN section loading FILE at hex ADDR (repeatable)")
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
    for addr, bin_path in args.bin:
        data = bin_path.read_bytes()
        if not data:
            print(f"error: {bin_path} is empty", file=sys.stderr)
            return 1
        if addr + len(data) > 0x10000:
            print(f"error: {bin_path} exceeds address space at {addr:04X}",
                  file=sys.stderr)
            return 1
        pbin = struct.pack("<II", addr, len(data)) + data
        container += struct.pack("<II", 0x4E494250, len(pbin)) + pbin  # PBIN
        print(f"  PBIN {addr:04X}-{addr + len(data) - 1:04X} "
              f"({len(data)} bytes from {bin_path})")
    Path(args.out).write_bytes(container)
    print(f"wrote {args.out}: {len(container)} bytes (BASIC {len(payload)} bytes,"
          f" {len(args.bin)} binary section(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
