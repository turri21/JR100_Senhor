#!/usr/bin/env python3
# ============================================================================
#
#  JR100_MiSTer: generate golden per-cycle VIA vectors from pyjr100emu.
#
#  Drives JR100R6522 with a scenario file and records the observable
#  state after every cycle (tick-then-access ordering, one priming tick,
#  identical to the HDL cycle model proven by the system lockstep).
#
#  Scenario format (one op per line, '#' comments):
#      N <total-cycles>
#      W <cycle> <reg-hex> <value-hex>
#      R <cycle> <reg-hex>
#
#  Output line per cycle:
#      C <k> t1=XXXX t2=XXXX ifr=XX ier=XX pb7=B pb6=B irq=B
#
#  Read return values are NOT compared (intra-cycle data timing differs
#  by design; side effects such as IFR clears are covered).
#
#  Copyright (C) 2026 Zabaglione
#  SPDX-License-Identifier: GPL-2.0-or-later
#
# ============================================================================
"""Generate golden VIA cycle vectors from the pyjr100emu reference."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EMU = Path(os.environ.get("JR100EMU_PATH", REPO.parent / "jr100emu"))
sys.path.insert(0, str(EMU / "src"))

from jr100emu.jr100.r6522 import JR100R6522  # noqa: E402


class _DisplayStub:
    FONT_NORMAL = 0
    FONT_USER_DEFINED = 1

    def set_current_font(self, plane: int) -> None:
        pass


class _KeyboardStub:
    def get_key_matrix(self):
        return [0] * 9


class _Hardware:
    def __init__(self) -> None:
        self.display = _DisplayStub()
        self.keyboard = _KeyboardStub()


class _Computer:
    def __init__(self) -> None:
        self.clock_count = 0
        self.hardware = _Hardware()


def parse_scenario(path: Path):
    total = 0
    ops = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if parts[0] == "N":
            total = int(parts[1])
        elif parts[0] == "W":
            ops.setdefault(int(parts[1]), []).append(("W", int(parts[2], 16), int(parts[3], 16)))
        elif parts[0] == "R":
            ops.setdefault(int(parts[1]), []).append(("R", int(parts[2], 16), 0))
        else:
            raise ValueError(f"bad scenario line: {raw}")
    return total, ops


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    total, ops = parse_scenario(Path(args.scenario))
    computer = _Computer()
    via = JR100R6522(computer, 0xC800)

    lines = []
    for k in range(total):
        computer.clock_count = k + 1
        # one tick per cycle; the extra priming tick lands on k=0
        via._execute(k + 1)  # noqa: SLF001
        for op, reg, value in ops.get(k, []):
            if op == "W":
                via.store8(0xC800 + reg, value)
            else:
                via.load8(0xC800 + reg)
        state = via._state  # noqa: SLF001
        irq = 1 if (state.IFR & state.IER & 0x7F) else 0
        lines.append(
            f"C {k} t1={state.timer1 & 0xFFFF:04X} t2={state.timer2 & 0xFFFF:04X}"
            f" ifr={state.IFR & 0xFF:02X} ier={state.IER & 0x7F:02X}"
            f" pb7={via.input_port_b_bit(7)} pb6={via.input_port_b_bit(6)} irq={irq}"
        )

    Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
