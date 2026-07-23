#!/usr/bin/env python3
# ============================================================================
#
#  JR100_MiSTer: PRG loader acceptance test.
#
#  For each PROG container, computes the exact byte writes the reference
#  loader (pyjr100emu load_prog) performs, streams the same file through
#  the RTL loader after a full BASIC boot in Vjr100_top, and compares
#  every written address.
#
#  Copyright (C) 2026 Zabaglione
#  SPDX-License-Identifier: GPL-2.0-or-later
#
# ============================================================================
"""Verify the RTL PROG loader against pyjr100emu's load_prog."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import trace_diff  # noqa: E402

EMU = Path(os.environ.get("JR100EMU_PATH", REPO.parent / "jr100emu"))
sys.path.insert(0, str(EMU / "src"))
from jr100emu.emulator.file.program import load_prog  # noqa: E402

WORK = REPO / "sim" / "work"
SIM = REPO / "sim" / "obj_dir" / "Vjr100_top"


class _RecordingMemory:
    def __init__(self) -> None:
        self.data: dict[int, int] = {}

    def store8(self, address: int, value: int) -> None:
        self.data[address & 0xFFFF] = value & 0xFF

    def store16(self, address: int, value: int) -> None:
        self.store8(address, (value >> 8) & 0xFF)
        self.store8(address + 1, value & 0xFF)

    def load8(self, address: int) -> int:
        return self.data.get(address & 0xFFFF, 0)


def expected_writes(prg: Path) -> dict[int, int]:
    memory = _RecordingMemory()
    load_prog(memory, prg)
    return memory.data


def ranges_for(addresses: list[int]) -> list[str]:
    ranges: list[str] = []
    start = prev = addresses[0]
    for addr in addresses[1:]:
        if addr > prev + 64:
            ranges.append(f"{start:04X}:{prev:04X}")
            start = addr
        prev = addr
    ranges.append(f"{start:04X}:{prev:04X}")
    return ranges


def check(prg: Path) -> bool:
    expect = expected_writes(prg)
    addresses = sorted(expect)
    dump = WORK / f"prg_{prg.stem}.dump"
    cmd = [str(SIM), "--image", str(WORK / "boot.img"), "--cycles", "600000",
           "--prg", str(prg), "--dump", str(dump)]
    for spec in ranges_for(addresses):
        cmd += ["--dump-range", spec]
    subprocess.run(cmd, check=True, capture_output=True)
    mem = trace_diff.parse_hex_dump(dump.read_text(encoding="utf-8").splitlines())
    bad = [(a, expect[a], mem.get(a)) for a in addresses if mem.get(a) != expect[a]]
    if bad:
        a, want, got = bad[0]
        print(f"FAIL {prg.name}: {len(bad)} bytes differ, first {a:04X}"
              f" want {want:02X} got {got if got is None else f'{got:02X}'}")
        return False
    print(f"PASS {prg.name} ({len(addresses)} bytes verified)")
    return True


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: run_prg_load_test.py <file.prg> [...]", file=sys.stderr)
        return 2
    ok = True
    for name in sys.argv[1:]:
        ok &= check(Path(name))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
