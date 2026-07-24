#!/usr/bin/env python3
# ============================================================================
#
#  JR100_MiSTer: virtual cassette deck acceptance (ROM-driven).
#
#  The BASIC ROM itself is the test driver: the harness types SAVE /
#  LOAD on the key matrix and the ROM's real cassette routines produce
#  and consume the FSK waveform through the VIA (CB2 out, CA1/CB1 in).
#
#    save:  boot -> load a .bas -> type SAVE -> the deck records the
#           byte stream; the tape header/checksums and the data block
#           are verified against the reference program bytes.
#    load:  fresh boot -> type LOAD -> play the recorded tape -> the
#           BASIC program area must match the reference exactly
#           (full ROM round trip).
#
#  Copyright (C) 2026 Zabaglione
#  SPDX-License-Identifier: GPL-2.0-or-later
#
# ============================================================================
"""ROM-driven SAVE/LOAD acceptance for the virtual cassette deck."""

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
from jr100emu.emulator.file.program import load_basic_text  # noqa: E402

WORK = REPO / "sim" / "work"
SIM = REPO / "sim" / "obj_dir" / "Vjr100_top"

# key matrix positions (row, col), from pyjr100emu KEY_MATRIX_MAP
KEYS = {
    "A": (1, 0), "S": (1, 1), "D": (1, 2), "E": (2, 2), "V": (7, 0),
    "L": (6, 3), "O": (5, 3), "M": (7, 3), "\n": (8, 3),
}
PRESS = 90000    # CPU cycles a key is held (the ROM clicks ~0.1s per key,
GAP = 90000      # so the cadence must stay slower than the click)


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


def key_args(text: str, start: int) -> tuple[list[str], int]:
    args = []
    t = start
    for ch in text:
        row, col = KEYS[ch.upper()]
        idx = row * 5 + col
        args += ["--key", f"{t}:{idx}:1", "--key", f"{t + PRESS}:{idx}:0"]
        t += PRESS + GAP
    return args, t


def golden_program(bas: Path) -> bytes:
    mem = _RecordingMemory()
    load_basic_text(mem, bas)
    end = ((mem.data[6] << 8) | mem.data[7]) - 2   # final data byte
    return bytes(mem.data.get(a, 0) for a in range(0x0246, end + 1))


def run_save(bas: Path, tape: Path) -> bool:
    prog = golden_program(bas)
    keys, _ = key_args("SAVE\n", 650000)
    # ROM SAVE: ~2.4M pre-delay + 6.2M leader + header + 255-bit gap +
    # (N+1) frames at 1520 cycles/bit
    cycles2 = 1300000 + 11000000 + (len(prog) + 40) * 11 * 1520 + 2000000
    cmd = [str(SIM), "--image", str(WORK / "boot.img"), "--cycles", "600000",
           "--bas", str(bas), "--cycles2", str(cycles2),
           "--tape", str(tape), "--tape-blank", "65536",
           "--tape-out", str(tape)] + keys
    tape.unlink(missing_ok=True)
    subprocess.run(cmd, check=True, capture_output=True)

    raw = tape.read_bytes()
    hdr = raw[:33]
    if sum(hdr[:32]) & 0xFF != hdr[32]:
        print(f"FAIL save {bas.name}: header checksum")
        return False
    start = (hdr[16] << 8) | hdr[17]
    length = (hdr[18] << 8) | hdr[19]
    if start != 0x0246:
        print(f"FAIL save {bas.name}: start {start:04X}")
        return False
    data = raw[33:33 + length]
    if sum(data) & 0xFF != raw[33 + length]:
        print(f"FAIL save {bas.name}: data checksum")
        return False
    if data[:len(prog)] != prog:
        diff = next(i for i in range(len(prog)) if data[i] != prog[i])
        print(f"FAIL save {bas.name}: data differs at +{diff}"
              f" want {prog[diff]:02X} got {data[diff]:02X}")
        return False
    print(f"PASS save {bas.name} (header ok, {length} data bytes,"
          f" checksums ok)")
    return True


def run_load(bas: Path, tape: Path) -> bool:
    prog = golden_program(bas)
    keys, t_end = key_args("LOAD\n", 650000)
    play_at = t_end + 50000
    raw = tape.read_bytes()
    length = (raw[18] << 8) | raw[19]
    cycles2 = (play_at - 600000) + (4080 + 255) * 1520 \
        + (34 + length + 1) * 11 * 1520 + 3000000
    dump = WORK / f"cmt_load_{bas.stem}.dump"
    cmd = [str(SIM), "--image", str(WORK / "boot.img"), "--cycles", "600000",
           "--cycles2", str(cycles2), "--tape", str(tape),
           "--tape-play-at", str(play_at),
           "--dump", str(dump), "--dump-range", "0000:07FF"] + keys
    subprocess.run(cmd, check=True, capture_output=True)

    mem = trace_diff.parse_hex_dump(dump.read_text(encoding="utf-8").splitlines())
    got = bytes(mem.get(0x0246 + i, 0) for i in range(len(prog)))
    if got != prog:
        diff = next(i for i in range(len(prog)) if got[i] != prog[i])
        print(f"FAIL load {bas.name}: memory differs at 0246+{diff:X}"
              f" want {prog[diff]:02X} got {got[diff]:02X}")
        return False
    print(f"PASS load {bas.name} ({len(prog)} bytes restored by the ROM)")
    return True


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: run_cmt_tests.py <file.bas> [...]", file=sys.stderr)
        return 2
    ok = True
    for name in sys.argv[1:]:
        bas = Path(name)
        tape = WORK / f"cmt_{bas.stem}.cmt"
        s = run_save(bas, tape)
        ok &= s
        if s:
            ok &= run_load(bas, tape)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
