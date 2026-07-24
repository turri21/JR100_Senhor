#!/usr/bin/env python3
# ============================================================================
#
#  JR100_MiSTer: create a blank save file for the OSD "Mount Save File"
#  slot. The file is a valid, empty PROG v2 container (zero-length PBAS
#  + CMNT padding) sized to a multiple of 512 bytes, so it can be
#  mounted for saving right away and also loads cleanly through
#  "Load PRG" before anything was saved into it.
#
#  Copyright (C) 2026 Zabaglione
#  SPDX-License-Identifier: GPL-2.0-or-later
#
# ============================================================================
"""Create a blank mountable save file (default 16 KiB)."""

from __future__ import annotations

import argparse
import struct
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", help="output .prg save file")
    parser.add_argument("--size", type=int, default=16384,
                        help="file size in bytes, multiple of 512 (default 16384)")
    args = parser.parse_args()

    if args.size % 512 or args.size < 512:
        parser.error("--size must be a positive multiple of 512")

    container = bytearray()
    container += b"PROG" + struct.pack("<I", 2)
    container += struct.pack("<II", 0x53414250, 4) + struct.pack("<I", 0)  # PBAS len 0
    cmnt_len = args.size - len(container) - 8
    container += struct.pack("<II", 0x544E4D43, cmnt_len) + struct.pack("<I", 0)
    container += bytes(cmnt_len - 4)

    Path(args.out).write_bytes(bytes(container))
    print(f"wrote {args.out}: {args.size} bytes (blank save container)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
