#!/usr/bin/env python3
# ============================================================================
#
#  JR100_MiSTer: dump the MB8861 opcode/cycle table from the reference
#  implementation (pyjr100emu). The Python table is the compatibility
#  baseline for the SystemVerilog CPU core (AGENTS.md §1, §3.1).
#
#  Copyright (C) 2026 Zabaglione
#  SPDX-License-Identifier: GPL-2.0-or-later
#
# ============================================================================
"""Dump opcode -> (cycles, handler) from pyjr100emu's MB8861.

Usage:
    JR100EMU_PATH=../jr100emu python3 tools/dump_opcode_table.py > docs/generated/opcode_cycles.txt

The reference checkout defaults to ../jr100emu (see docs/DEVELOPMENT.md).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    default_ref = repo_root.parent / "jr100emu"
    ref_path = Path(os.environ.get("JR100EMU_PATH", str(default_ref)))
    src = ref_path / "src"
    if not src.is_dir():
        print(f"error: pyjr100emu not found at {ref_path} (set JR100EMU_PATH)", file=sys.stderr)
        return 2
    sys.path.insert(0, str(src))

    from jr100emu.cpu.cpu import MB8861  # noqa: PLC0415
    from jr100emu.memory import MemorySystem, RAM  # noqa: PLC0415

    memory = MemorySystem()
    memory.allocate_space(0x10000)
    memory.register_memory(RAM(0x0000, 0x10000))

    class DummyComputer:
        def __init__(self, mem: MemorySystem) -> None:
            self.hardware = type("Hardware", (), {"memory": mem})()
            self.clock_count = 0

    cpu = MB8861(DummyComputer(memory))
    table = cpu._opcode_table  # noqa: SLF001

    print("# MB8861 opcode cycle table extracted from pyjr100emu (compatibility baseline)")
    print("# opcode cycles handler")
    for opcode in sorted(table):
        handler, cycles = table[opcode]
        print(f"{opcode:02X} {cycles} {handler.__name__}")
    # Opcodes handled outside the table by the execute() loop:
    print("# special-cased by execute():")
    print(f"{MB8861.OP_RTI_IMP:02X} 10 _rti")
    print(f"{MB8861.OP_RTS_IMP:02X} 5 _rts")
    print(f"{MB8861.OP_SWI_IMP:02X} 12 _swi")
    print(f"{MB8861.OP_WAI_IMP:02X} 9 _wai")
    print("# undefined opcodes execute as a 1-cycle NOP")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
