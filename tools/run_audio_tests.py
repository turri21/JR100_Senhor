#!/usr/bin/env python3
# ============================================================================
#
#  JR100_MiSTer: audio band-limiting acceptance tests (AGENTS.md §3.4/§5.2).
#
#  A tiny test ROM configures ACR=E0 (Timer 1 mode 3, PB7 square wave)
#  and starts Timer 1 with a given latch value. The harness records the
#  band-limited audio output transitions at CPU-cycle resolution.
#
#  Checks:
#    - in-band latch: audio toggles with half-period latch+2 CPU cycles
#    - out-of-band latch: audio stays silent while the VIA keeps
#      running (t1 keeps counting in the trace)
#
#  Copyright (C) 2026 Zabaglione
#  SPDX-License-Identifier: GPL-2.0-or-later
#
# ============================================================================
"""Run the audio band-limiting acceptance suite against Vjr100_top."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WORK = REPO / "sim" / "work"
SIM = REPO / "sim" / "obj_dir" / "Vjr100_top"


def build_image(path: Path, latch: int) -> None:
    code = bytes([
        0x86, 0xE0,              # LDAA #$E0
        0xB7, 0xC8, 0x0B,        # STAA $C80B  (ACR)
        0x86, latch & 0xFF,      # LDAA #latch
        0xB7, 0xC8, 0x04,        # STAA $C804  (T1 latch low)
        0x86, 0x00,              # LDAA #$00
        0xB7, 0xC8, 0x05,        # STAA $C805  (T1CH: start)
        0x20, 0xFE,              # BRA *
    ])
    image = bytearray(0x10000)
    image[0xE400:0xE400 + len(code)] = code
    image[0xFFFE] = 0xE4
    image[0xFFFF] = 0x00
    path.write_bytes(bytes(image))


def build_image_acr_after(path: Path, latch: int) -> None:
    # BASIC POKE order (doremi_scale.bas): T1 is written and started with
    # ACR still 0 (one-shot), the first timeout passes, and only then is
    # ACR set to E0. The reference sound model turns the line on at the
    # next Timer 1 reload, so the tone must still be produced.
    code = bytes([
        0x86, latch & 0xFF,      # LDAA #latch
        0xB7, 0xC8, 0x04,        # STAA $C804  (T1 latch low)
        0x86, 0x00,              # LDAA #$00
        0xB7, 0xC8, 0x05,        # STAA $C805  (T1CH: start, one-shot)
        0xCE, 0x00, 0x40,        # LDX #$0040  (wait ~512 cycles > timeout)
        0x09,                    # DEX
        0x26, 0xFD,              # BNE -3
        0x86, 0xE0,              # LDAA #$E0
        0xB7, 0xC8, 0x0B,        # STAA $C80B  (ACR, after the timeout)
        0x20, 0xFE,              # BRA *
    ])
    image = bytearray(0x10000)
    image[0xE400:0xE400 + len(code)] = code
    image[0xFFFE] = 0xE4
    image[0xFFFF] = 0x00
    path.write_bytes(bytes(image))


def run(latch: int, name: str) -> tuple[list[tuple[int, int]], Path]:
    image = WORK / f"audio_{name}.img"
    if name == "acr_after":
        build_image_acr_after(image, latch)
    else:
        build_image(image, latch)
    audio = WORK / f"audio_{name}.txt"
    trace = WORK / f"audio_{name}.trace"
    subprocess.run(
        [str(SIM), "--image", str(image), "--cycles", "3000",
         "--audio", str(audio), "--trace", str(trace)],
        check=True, capture_output=True,
    )
    events = []
    for line in audio.read_text(encoding="utf-8").splitlines():
        cycle, level = line.split()
        events.append((int(cycle), int(level)))
    return events, trace


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    failed = 0

    # In-band: latch=100 -> half period 102 CPU cycles (~4.3 kHz).
    # The snd flop toggles on every T1 reload, so edges before the T1CH
    # write (free-running reloads during setup) are start-up transients;
    # judge the steady state.
    events, _ = run(100, "inband")
    toggles = [c for c, _ in events]
    periods = [b - a for a, b in zip(toggles[2:], toggles[3:])]
    if len(periods) >= 8 and all(p == 102 for p in periods[:8]):
        print(f"PASS inband   (half period 102 cycles x{len(periods)})")
    else:
        print(f"FAIL inband: periods={periods[:8]}")
        failed = 1

    # ACR set after T1 started (BASIC POKE order): tone must appear
    events, _ = run(100, "acr_after")
    toggles = [c for c, _ in events]
    periods = [b - a for a, b in zip(toggles[1:], toggles[2:])]
    if len(periods) >= 8 and all(p == 102 for p in periods[:8]):
        print(f"PASS acr_after (half period 102 cycles x{len(periods)})")
    else:
        print(f"FAIL acr_after: events={len(events)} periods={periods[:8]}")
        failed = 1

    # Out-of-band: latch=5 (~63 kHz) -> silence, VIA keeps counting
    events, trace = run(5, "outband")
    silent = all(level == 0 for _, level in events)
    t1_values = set()
    for line in trace.read_text(encoding="utf-8").splitlines():
        if line.startswith("S "):
            for token in line.split():
                if token.startswith("t1="):
                    t1_values.add(token)
    if silent and len(t1_values) > 4:
        print(f"PASS outband  (silent, t1 still counting: {len(t1_values)} distinct values)")
    else:
        print(f"FAIL outband: silent={silent} t1_distinct={len(t1_values)}")
        failed = 1

    return failed


if __name__ == "__main__":
    raise SystemExit(main())
