#!/usr/bin/env python3
# ============================================================================
#
#  JR100_MiSTer instruction-boundary trace comparator (docs/TRACE_FORMAT.md v1)
#
#  Copyright (C) 2026 Zabaglione
#
#  This program is free software; you can redistribute it and/or modify it
#  under the terms of the GNU General Public License as published by the Free
#  Software Foundation; either version 2 of the License, or (at your option)
#  any later version.
#
# ============================================================================
"""Compare two instruction-boundary traces (and optional memory dumps).

Usage:
    trace_diff.py REF_TRACE DUT_TRACE [--mem REF_DUMP DUT_DUMP] [--context N]

Exit codes: 0 = identical, 1 = divergence found, 2 = bad input.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


TRACE_FIELDS = (
    "n", "clk", "pc", "a", "b", "ix", "sp", "cc",
    "ora", "orb", "ddra", "ddrb", "acr", "pcr", "ifr", "ier", "sr",
    "t1", "t1l", "t2", "t2l",
)


class TraceFormatError(ValueError):
    """Raised when a trace line does not follow docs/TRACE_FORMAT.md."""


@dataclass(frozen=True)
class Sample:
    lineno: int
    raw: str
    fields: Dict[str, str]


@dataclass
class Divergence:
    sample_n: str = ""
    lineno_ref: int = 0
    lineno_dut: int = 0
    raw_ref: str = ""
    raw_dut: str = ""
    mismatches: List[Tuple[str, str, str]] = field(default_factory=list)
    length_mismatch: bool = False
    ref_count: int = 0
    dut_count: int = 0


def parse_trace(lines: Iterable[str]) -> List[Sample]:
    samples: List[Sample] = []
    for lineno, line in enumerate(lines, start=1):
        text = line.rstrip("\n")
        if not text or text.startswith("#"):
            continue
        if not text.startswith("S "):
            raise TraceFormatError(f"line {lineno}: unknown record: {text!r}")
        fields: Dict[str, str] = {}
        for token in text[2:].split(" "):
            key, sep, value = token.partition("=")
            if not sep or not key or not value:
                raise TraceFormatError(f"line {lineno}: malformed token {token!r}")
            fields[key] = value
        missing = [key for key in TRACE_FIELDS if key not in fields]
        if missing:
            raise TraceFormatError(f"line {lineno}: missing fields {missing}")
        samples.append(Sample(lineno=lineno, raw=text, fields=fields))
    return samples


def compare_traces(ref: Sequence[Sample], dut: Sequence[Sample]) -> Optional[Divergence]:
    for sample_ref, sample_dut in zip(ref, dut):
        mismatches = [
            (key, sample_ref.fields[key], sample_dut.fields[key])
            for key in TRACE_FIELDS
            if sample_ref.fields[key] != sample_dut.fields[key]
        ]
        if mismatches:
            return Divergence(
                sample_n=sample_ref.fields["n"],
                lineno_ref=sample_ref.lineno,
                lineno_dut=sample_dut.lineno,
                raw_ref=sample_ref.raw,
                raw_dut=sample_dut.raw,
                mismatches=mismatches,
            )
    if len(ref) != len(dut):
        return Divergence(
            length_mismatch=True,
            ref_count=len(ref),
            dut_count=len(dut),
        )
    return None


def parse_hex_dump(lines: Iterable[str]) -> Dict[int, int]:
    """Parse the debug_runner hex dump table into {address: byte}."""
    data: Dict[int, int] = {}
    for lineno, line in enumerate(lines, start=1):
        text = line.strip()
        if not text or text.startswith("ADDR"):
            continue
        parts = text.split()
        if len(parts) != 17:
            raise TraceFormatError(f"dump line {lineno}: expected 17 columns: {text!r}")
        try:
            base = int(parts[0], 16)
            values = [int(value, 16) for value in parts[1:]]
        except ValueError as exc:
            raise TraceFormatError(f"dump line {lineno}: {exc}") from exc
        for offset, value in enumerate(values):
            data[(base + offset) & 0xFFFF] = value & 0xFF
    return data


def compare_dumps(ref: Dict[int, int], dut: Dict[int, int]) -> List[Tuple[int, int, int]]:
    diffs: List[Tuple[int, int, int]] = []
    for address in sorted(set(ref) | set(dut)):
        value_ref = ref.get(address, -1)
        value_dut = dut.get(address, -1)
        if value_ref != value_dut:
            diffs.append((address, value_ref, value_dut))
    return diffs


def _print_trace_divergence(divergence: Divergence, ref: Sequence[Sample], context: int) -> None:
    if divergence.length_mismatch:
        print(
            "TRACE LENGTH MISMATCH:"
            f" ref has {divergence.ref_count} samples,"
            f" dut has {divergence.dut_count} samples"
        )
        return
    print(
        f"TRACE DIVERGENCE at sample n={divergence.sample_n}"
        f" (ref line {divergence.lineno_ref}, dut line {divergence.lineno_dut})"
    )
    for key, value_ref, value_dut in divergence.mismatches:
        print(f"  field {key}: ref={value_ref} dut={value_dut}")
    if context > 0:
        index = next(
            (i for i, sample in enumerate(ref) if sample.lineno == divergence.lineno_ref),
            None,
        )
        if index is not None:
            for sample in ref[max(0, index - context):index]:
                print(f"  ctx: {sample.raw}")
    print(f"  ref: {divergence.raw_ref}")
    print(f"  dut: {divergence.raw_dut}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="trace_diff",
        description="Compare two instruction-boundary traces (docs/TRACE_FORMAT.md v1).",
    )
    parser.add_argument("ref", help="Reference trace file (pyjr100emu)")
    parser.add_argument("dut", help="Device-under-test trace file (Verilator)")
    parser.add_argument(
        "--mem",
        nargs=2,
        metavar=("REF_DUMP", "DUT_DUMP"),
        default=None,
        help="Also compare a pair of hex memory dumps",
    )
    parser.add_argument(
        "--context",
        type=int,
        default=3,
        help="Reference samples to print before the divergence (default 3)",
    )
    args = parser.parse_args(argv)

    try:
        ref = parse_trace(Path(args.ref).read_text(encoding="utf-8").splitlines())
        dut = parse_trace(Path(args.dut).read_text(encoding="utf-8").splitlines())
        mem_diffs: List[Tuple[int, int, int]] = []
        if args.mem is not None:
            ref_dump = parse_hex_dump(Path(args.mem[0]).read_text(encoding="utf-8").splitlines())
            dut_dump = parse_hex_dump(Path(args.mem[1]).read_text(encoding="utf-8").splitlines())
            mem_diffs = compare_dumps(ref_dump, dut_dump)
    except (OSError, TraceFormatError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    divergence = compare_traces(ref, dut)
    failed = False
    if divergence is not None:
        _print_trace_divergence(divergence, ref, args.context)
        failed = True
    if mem_diffs:
        print(f"MEMORY MISMATCH at {len(mem_diffs)} address(es):")
        for address, value_ref, value_dut in mem_diffs[:32]:
            ref_text = f"{value_ref:02X}" if value_ref >= 0 else "--"
            dut_text = f"{value_dut:02X}" if value_dut >= 0 else "--"
            print(f"  {address:04X}: ref={ref_text} dut={dut_text}")
        if len(mem_diffs) > 32:
            print(f"  ... and {len(mem_diffs) - 32} more")
        failed = True

    if failed:
        return 1
    print(f"OK: {len(ref)} samples match" + (", memory matches" if args.mem else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
