#!/usr/bin/env python3
# ============================================================================
#
#  JR100_MiSTer: add an autostart hint to an existing PROG (.prg) file.
#
#  Writes (or extends) the v2 CMNT section with "USR=$HHHH"; when the
#  core's OSD Autostart option is on, it types A=USR($HHHH) after the
#  load. v1 containers are converted to v2 (PNAM + PBAS/PBIN), which
#  every parser in the ecosystem reads.
#
#  Copyright (C) 2026 Zabaglione
#  SPDX-License-Identifier: GPL-2.0-or-later
#
# ============================================================================
"""Add a "USR=$HHHH" autostart hint to a PROG container."""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

PNAM, PBAS, PBIN, CMNT = 0x4D414E50, 0x53414250, 0x4E494250, 0x544E4D43


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("infile")
    parser.add_argument("outfile")
    parser.add_argument("addr", help="machine-code entry address (hex)")
    args = parser.parse_args()

    entry = int(args.addr.lstrip("$"), 16)
    if not 0 <= entry <= 0xFFFF:
        parser.error("address out of range")
    marker = f"USR=${entry:04X}"

    raw = Path(args.infile).read_bytes()
    if raw[:4] != b"PROG":
        print("error: not a PROG file", file=sys.stderr)
        return 1
    version = struct.unpack_from("<I", raw, 4)[0]

    sections: list[tuple[int, bytes]] = []
    comment = ""
    if version == 1:
        pos = 8
        name_len = struct.unpack_from("<I", raw, pos)[0]
        name = raw[pos + 4:pos + 4 + name_len]
        pos += 4 + name_len
        start, length, flag = struct.unpack_from("<III", raw, pos)
        pos += 12
        payload = raw[pos:pos + length]
        if name:
            sections.append((PNAM, struct.pack("<I", len(name)) + name))
        if flag == 0:
            sections.append((PBAS, struct.pack("<I", len(payload)) + payload))
        else:
            sections.append(
                (PBIN, struct.pack("<II", start, len(payload)) + payload))
    elif version == 2:
        pos = 8
        while pos + 8 <= len(raw):
            sec_id, sec_len = struct.unpack_from("<II", raw, pos)
            payload = raw[pos + 8:pos + 8 + sec_len]
            pos += 8 + sec_len
            if sec_id == CMNT and not comment:
                clen = struct.unpack_from("<I", payload, 0)[0]
                comment = payload[4:4 + clen].decode("utf-8", "replace")
            else:
                sections.append((sec_id, payload))
    else:
        print(f"error: unsupported PROG version {version}", file=sys.stderr)
        return 1

    text = (comment + " " + marker).strip() if marker not in comment else comment
    note = text.encode("utf-8")
    sections.append((CMNT, struct.pack("<I", len(note)) + note))

    out = bytearray(b"PROG" + struct.pack("<I", 2))
    for sec_id, payload in sections:
        out += struct.pack("<II", sec_id, len(payload)) + payload
    Path(args.outfile).write_bytes(bytes(out))
    print(f"wrote {args.outfile}: autostart {marker}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
