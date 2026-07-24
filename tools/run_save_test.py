#!/usr/bin/env python3
# ============================================================================
#
#  JR100_MiSTer: OSD "Save BASIC to file" acceptance test.
#
#  Boots the core, loads a BASIC text file through the .bas loader,
#  triggers the saver against an emulated mounted image, and verifies:
#    1. pyjr100emu's load_prog parses the saved container and reproduces
#       exactly the memory the reference's load_basic_text would create
#       (program bytes, DF terminators and workspace pointers), and
#    2. the RTL PRG loader accepts the saved file byte-identically
#       (round trip through the core's own loader).
#  Also saves with no program loaded and checks the empty container.
#
#  Copyright (C) 2026 Zabaglione
#  SPDX-License-Identifier: GPL-2.0-or-later
#
# ============================================================================
"""Round-trip acceptance for the OSD BASIC saver."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import run_prg_load_test  # noqa: E402

EMU = Path(os.environ.get("JR100EMU_PATH", REPO.parent / "jr100emu"))
sys.path.insert(0, str(EMU / "src"))
from jr100emu.emulator.file.program import load_basic_text, load_prog  # noqa: E402

WORK = REPO / "sim" / "work"
SIM = REPO / "sim" / "obj_dir" / "Vjr100_top"
SAVE_SIZE = 16384


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


def save_via_core(bas: Path | None, out: Path) -> None:
    cmd = [str(SIM), "--image", str(WORK / "boot.img"), "--cycles", "600000",
           "--save-file", str(out), "--save-size", str(SAVE_SIZE)]
    if bas is not None:
        cmd += ["--bas", str(bas)]
    subprocess.run(cmd, check=True, capture_output=True)


def check(bas: Path) -> bool:
    golden = _RecordingMemory()
    load_basic_text(golden, bas)

    out = WORK / f"save_{bas.stem}.img"
    save_via_core(bas, out)
    if out.stat().st_size != SAVE_SIZE:
        print(f"FAIL {bas.name}: saved image is {out.stat().st_size} bytes")
        return False

    saved = _RecordingMemory()
    load_prog(saved, out)
    bad = [a for a in sorted(golden.data)
           if saved.data.get(a) != golden.data[a]]
    if bad:
        a = bad[0]
        print(f"FAIL {bas.name}: {len(bad)} bytes differ after reload,"
              f" first {a:04X} want {golden.data[a]:02X}"
              f" got {saved.data.get(a)}")
        return False

    if not run_prg_load_test.check(out):
        print(f"FAIL {bas.name}: RTL loader round trip")
        return False
    print(f"PASS save {bas.name} ({len(golden.data)} bytes round-tripped)")
    return True


def check_empty() -> bool:
    out = WORK / "save_empty.img"
    save_via_core(None, out)
    saved = _RecordingMemory()
    info = load_prog(saved, out)
    region = info.address_regions[0] if info.address_regions else None
    if info.basic_area and region and region.end == 0x0245:
        print("PASS save empty (zero-length BASIC container)")
        return True
    print(f"FAIL empty: basic_area={info.basic_area} regions={info.address_regions}")
    return False


def main() -> int:
    ok = check_empty()
    for name in sys.argv[1:]:
        ok &= check(Path(name))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
