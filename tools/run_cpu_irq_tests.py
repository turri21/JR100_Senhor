#!/usr/bin/env python3
# ============================================================================
#
#  JR100_MiSTer: CPU interrupt / WAI path verification.
#
#  Each scenario builds a small machine-language program (shared between
#  both sides), generates a golden instruction-boundary trace by driving
#  pyjr100emu's MB8861 directly (set_irq_line / nmi at instruction
#  boundaries), runs the CPU-only Verilator harness with the same
#  boundary-synchronised events, and diffs with trace_diff --cpu-only.
#
#  Covers: level IRQ entry (I set, 12 cycles, storm on RTI with the
#  line held), IRQ masking by SEI/CLI, WAI stacking + 4-cycle IRQ exit,
#  NMI, and SWI/RTI.
#
#  Copyright (C) 2026 Zabaglione
#  SPDX-License-Identifier: GPL-2.0-or-later
#
# ============================================================================
"""Verify the HDL CPU interrupt/WAI paths against pyjr100emu."""

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
from jr100emu.cpu.cpu import MB8861  # noqa: E402
from jr100emu.memory import MemorySystem, RAM  # noqa: E402

WORK = REPO / "sim" / "work"
SIM = REPO / "sim" / "obj_dir" / "Vmb8861"

RESET_VECTOR = 0xE400
HANDLER = 0xE500


def build_image(main_code: bytes, handler_code: bytes) -> bytes:
    image = bytearray(0x10000)
    image[RESET_VECTOR:RESET_VECTOR + len(main_code)] = main_code
    image[HANDLER:HANDLER + len(handler_code)] = handler_code
    for vector in (0xFFF8, 0xFFFA, 0xFFFC):    # IRQ, SWI, NMI -> handler
        image[vector] = HANDLER >> 8
        image[vector + 1] = HANDLER & 0xFF
    image[0xFFFE] = RESET_VECTOR >> 8
    image[0xFFFF] = RESET_VECTOR & 0xFF
    return bytes(image)


PROGRAMS = {
    # LDS #$01FF; CLI; loop: INCA; BRA loop  /  handler: INCB; RTI
    "irq_level": (
        bytes([0x8E, 0x01, 0xFF, 0x0E, 0x4C, 0x20, 0xFD]),
        bytes([0x5C, 0x3B]),
        ["--irq-at", "60:1", "--irq-at", "220:0"],
        [(60, "irq", True), (220, "irq", False)],
    ),
    # LDS; SEI; loop  (masked) then CLI via handler-less window:
    # LDS #$01FF; SEI; INCA x4; CLI; loop: INCA; BRA loop
    "irq_masked": (
        bytes([0x8E, 0x01, 0xFF, 0x0F, 0x4C, 0x4C, 0x4C, 0x4C, 0x0E,
               0x4C, 0x20, 0xFD]),
        bytes([0x5C, 0x3B]),
        ["--irq-at", "8:1", "--irq-at", "150:0"],
        [(8, "irq", True), (150, "irq", False)],
    ),
    # LDS #$01FF; CLI; WAI; INCA; loop: BRA loop
    "wai_irq": (
        bytes([0x8E, 0x01, 0xFF, 0x0E, 0x3E, 0x4C, 0x20, 0xFE]),
        bytes([0x5C, 0x3B]),
        ["--irq-at", "80:1", "--irq-at", "120:0"],
        [(80, "irq", True), (120, "irq", False)],
    ),
    # LDS #$01FF; loop: INCA; BRA loop  with an NMI pulse (I stays set)
    "nmi": (
        bytes([0x8E, 0x01, 0xFF, 0x4C, 0x20, 0xFD]),
        bytes([0x5C, 0x3B]),
        ["--nmi-at", "50"],
        [(50, "nmi", True)],
    ),
    # LDS #$01FF; SWI; INCA; loop: BRA loop
    "swi_rti": (
        bytes([0x8E, 0x01, 0xFF, 0x3F, 0x4C, 0x20, 0xFE]),
        bytes([0x5C, 0x3B]),
        [],
        [],
    ),
}

CYCLES = 400


class _Computer:
    def __init__(self, memory: MemorySystem) -> None:
        self.hardware = type("HW", (), {"memory": memory})()
        self.clock_count = 0


def golden_trace(image: bytes, events, out: Path) -> None:
    memory = MemorySystem()
    memory.allocate_space(0x10000)
    ram = RAM(0x0000, 0x10000)
    ram.data = list(image)
    memory.register_memory(ram)

    computer = _Computer(memory)
    cpu = MB8861(computer)
    cpu.registers.program_counter = (image[0xFFFE] << 8) | image[0xFFFF]
    cpu.registers.stack_pointer = 0x0000
    cpu.registers.acc_a = 0
    cpu.registers.acc_b = 0
    cpu.registers.index = 0
    cpu.flags.carry_i = True     # boot convention CC=D0

    pending = sorted(events)
    lines = ["# jr100-trace v1", "# generator: cpu irq golden"]
    n = 0
    while computer.clock_count < CYCLES:
        while pending and computer.clock_count >= pending[0][0]:
            _, kind, level = pending.pop(0)
            if kind == "irq":
                cpu.set_irq_line(level)
            else:
                cpu.nmi()
        cpu.execute(1)
        n += 1
        regs = cpu.registers
        cc = 0xC0
        for bit, flag in ((0x20, cpu.flags.carry_h), (0x10, cpu.flags.carry_i),
                          (0x08, cpu.flags.carry_n), (0x04, cpu.flags.carry_z),
                          (0x02, cpu.flags.carry_v), (0x01, cpu.flags.carry_c)):
            if flag:
                cc |= bit
        lines.append(
            f"S n={n} clk={computer.clock_count}"
            f" pc={regs.program_counter & 0xFFFF:04X}"
            f" a={regs.acc_a & 0xFF:02X} b={regs.acc_b & 0xFF:02X}"
            f" ix={regs.index & 0xFFFF:04X} sp={regs.stack_pointer & 0xFFFF:04X}"
            f" cc={cc:02X}"
            " ora=00 orb=00 ddra=00 ddrb=00 acr=00 pcr=00 ifr=00 ier=00 sr=00"
            " t1=0000 t1l=0000 t2=0000 t2l=0000"
        )
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    failed = 0
    for name, (main_code, handler_code, sim_args, events) in PROGRAMS.items():
        image = build_image(main_code, handler_code)
        image_path = WORK / f"irq_{name}.img"
        image_path.write_bytes(image)

        golden = WORK / f"irq_{name}.golden.trace"
        golden_trace(image, events, golden)

        dut = WORK / f"irq_{name}.dut.trace"
        pc = (image[0xFFFE] << 8) | image[0xFFFF]
        subprocess.run(
            [str(SIM), "--image", str(image_path), "--pc", f"{pc:04X}",
             "--sp", "0000", "--cc", "D0", "--cycles", str(CYCLES),
             "--trace", str(dut), *sim_args],
            check=True, capture_output=True,
        )

        result = subprocess.run(
            [sys.executable, str(REPO / "tools" / "trace_diff.py"),
             str(golden), str(dut), "--cpu-only"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            print(f"PASS {name:11s} ({result.stdout.strip()})")
        else:
            print(f"FAIL {name}:")
            print("\n".join(result.stdout.splitlines()[:6]))
            failed = 1
    return failed


if __name__ == "__main__":
    raise SystemExit(main())
