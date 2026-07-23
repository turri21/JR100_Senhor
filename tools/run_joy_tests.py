#!/usr/bin/env python3
# ============================================================================
#
#  JR100_MiSTer: joystick (CC02) acceptance tests, AGENTS.md §5.2.
#
#  Builds a tiny test ROM that samples $CC02 into $0100-$01FF, runs the
#  real-core-structure simulation (Vjr100_top) for each required input
#  pattern, and checks the sampled values: idle, each direction, each
#  diagonal, switch alone, direction+switch, hold, and release.
#
#  Copyright (C) 2026 Zabaglione
#  SPDX-License-Identifier: GPL-2.0-or-later
#
# ============================================================================
"""Run the CC02 joystick acceptance suite against Vjr100_top."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import trace_diff  # noqa: E402

WORK = REPO / "sim" / "work"
SIM = REPO / "sim" / "obj_dir" / "Vjr100_top"

# LDX #$0100; loop: LDAA $CC02; STAA 0,X; INX; CPX #$0200; BNE loop; BRA *
TEST_CODE = bytes(
    [0xCE, 0x01, 0x00,
     0xB6, 0xCC, 0x02,
     0xA7, 0x00,
     0x08,
     0x8C, 0x02, 0x00,
     0x26, 0xF5,
     0x20, 0xFE]
)

PATTERNS = {
    "idle":         0x00,
    "right":        0x01,
    "left":         0x02,
    "up":           0x04,
    "down":         0x08,
    "switch":       0x10,
    "up_right":     0x05,
    "down_right":   0x09,
    "up_left":      0x06,
    "down_left":    0x0A,
    "right_switch": 0x11,
}


def build_image(path: Path) -> None:
    image = bytearray(0x10000)
    image[0xE400:0xE400 + len(TEST_CODE)] = TEST_CODE
    image[0xFFFE] = 0xE4
    image[0xFFFF] = 0x00
    path.write_bytes(bytes(image))


def run_sim(image: Path, dump: Path, *extra: str) -> None:
    subprocess.run(
        [str(SIM), "--image", str(image), "--cycles", "8000",
         "--dump", str(dump), "--dump-range", "0100:01FF", *extra],
        check=True, capture_output=True,
    )


def samples(dump: Path) -> list[int]:
    mem = trace_diff.parse_hex_dump(dump.read_text(encoding="utf-8").splitlines())
    return [mem[0x0100 + i] for i in range(256)]


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    image = WORK / "joy_test.img"
    build_image(image)
    failed = 0

    for name, value in PATTERNS.items():
        dump = WORK / f"joy_{name}.dump"
        run_sim(image, dump, "--joy", f"{value:02X}")
        got = samples(dump)
        if all(v == value for v in got):
            print(f"PASS {name:13s} (0x{value:02X} x256)")
        else:
            bad = next((i, v) for i, v in enumerate(got) if v != value)
            print(f"FAIL {name}: sample[{bad[0]}]=0x{bad[1]:02X} expected 0x{value:02X}")
            failed = 1

    # hold then release: 0x11 held, released to 0x00 mid-run
    dump = WORK / "joy_release.dump"
    run_sim(image, dump, "--joy", "11", "--joy2", "00", "--joy2-at", "3000")
    got = samples(dump)
    held = got[:got.index(0x00)] if 0x00 in got else []
    ok = (len(held) > 10
          and all(v == 0x11 for v in held)
          and all(v == 0x00 for v in got[len(held):]))
    if ok:
        print(f"PASS hold_release   (0x11 x{len(held)} -> 0x00 x{256 - len(held)})")
    else:
        print(f"FAIL hold_release: {['%02X' % v for v in got[:16]]}...")
        failed = 1

    return failed


if __name__ == "__main__":
    raise SystemExit(main())
