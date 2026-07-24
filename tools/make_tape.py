#!/usr/bin/env python3
# ============================================================================
#
#  JR100_MiSTer: create a blank virtual cassette tape (.cmt) for the
#  OSD "Mount Tape" slot. The file holds raw tape bytes (33-byte header
#  block + program data + checksums, as the ROM's SAVE writes them);
#  a blank tape is simply zeros.
#
#  Copyright (C) 2026 Zabaglione
#  SPDX-License-Identifier: GPL-2.0-or-later
#
# ============================================================================
"""Create a blank .cmt tape file (default 64 KiB)."""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", help="output .cmt tape file")
    parser.add_argument("--size", type=int, default=65536,
                        help="file size in bytes (default 65536)")
    args = parser.parse_args()
    if args.size <= 0:
        parser.error("--size must be positive")
    Path(args.out).write_bytes(bytes(args.size))
    print(f"wrote {args.out}: {args.size} bytes (blank tape)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
