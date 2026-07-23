"""Tests for tools/trace_diff.py (docs/TRACE_FORMAT.md v1)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import trace_diff  # noqa: E402


SAMPLE_A = "S n=1 clk=19 pc=0301 a=01 b=00 ix=0000 sp=0244 cc=C0 ora=00 orb=00 ddra=00 ddrb=00 acr=00 pcr=00 ifr=00 ier=00 sr=00 t1=0000 t1l=0000 t2=0000 t2l=0000"
SAMPLE_B = "S n=2 clk=21 pc=0302 a=02 b=00 ix=0000 sp=0244 cc=C0 ora=00 orb=00 ddra=00 ddrb=00 acr=00 pcr=00 ifr=00 ier=00 sr=00 t1=0000 t1l=0000 t2=0000 t2l=0000"


def _trace(*lines: str) -> str:
    return "\n".join(("# jr100-trace v1",) + lines) + "\n"


class ParseTraceTest(unittest.TestCase):
    def test_skips_comment_lines_and_parses_fields(self) -> None:
        samples = trace_diff.parse_trace(_trace(SAMPLE_A).splitlines())
        self.assertEqual(len(samples), 1)
        self.assertEqual(samples[0].lineno, 2)
        self.assertEqual(samples[0].fields["n"], "1")
        self.assertEqual(samples[0].fields["pc"], "0301")
        self.assertEqual(samples[0].fields["t2l"], "0000")

    def test_rejects_malformed_record(self) -> None:
        with self.assertRaises(trace_diff.TraceFormatError):
            trace_diff.parse_trace(["S n=1 broken"])


class CompareTracesTest(unittest.TestCase):
    def test_identical_traces_have_no_divergence(self) -> None:
        a = trace_diff.parse_trace(_trace(SAMPLE_A, SAMPLE_B).splitlines())
        b = trace_diff.parse_trace(_trace(SAMPLE_A, SAMPLE_B).splitlines())
        self.assertIsNone(trace_diff.compare_traces(a, b))

    def test_detects_field_mismatch(self) -> None:
        mutated = SAMPLE_B.replace("a=02", "a=03")
        a = trace_diff.parse_trace(_trace(SAMPLE_A, SAMPLE_B).splitlines())
        b = trace_diff.parse_trace(_trace(SAMPLE_A, mutated).splitlines())
        divergence = trace_diff.compare_traces(a, b)
        self.assertIsNotNone(divergence)
        self.assertEqual(divergence.sample_n, "2")
        self.assertEqual(divergence.mismatches, [("a", "02", "03")])

    def test_detects_length_mismatch(self) -> None:
        a = trace_diff.parse_trace(_trace(SAMPLE_A, SAMPLE_B).splitlines())
        b = trace_diff.parse_trace(_trace(SAMPLE_A).splitlines())
        divergence = trace_diff.compare_traces(a, b)
        self.assertIsNotNone(divergence)
        self.assertTrue(divergence.length_mismatch)


class HexDumpTest(unittest.TestCase):
    DUMP = "\n".join(
        [
            "ADDR +0 +1 +2 +3 +4 +5 +6 +7 +8 +9 +A +B +C +D +E +F",
            "0300 4C 4C 20 FE 00 00 00 00 00 00 00 00 00 00 00 00",
        ]
    )

    def test_parse_hex_dump(self) -> None:
        data = trace_diff.parse_hex_dump(self.DUMP.splitlines())
        self.assertEqual(data[0x0300], 0x4C)
        self.assertEqual(data[0x0303], 0xFE)
        self.assertEqual(len(data), 16)

    def test_compare_dumps_reports_differing_addresses(self) -> None:
        a = trace_diff.parse_hex_dump(self.DUMP.splitlines())
        b = dict(a)
        b[0x0302] = 0x21
        diffs = trace_diff.compare_dumps(a, b)
        self.assertEqual(diffs, [(0x0302, 0x20, 0x21)])


class MainTest(unittest.TestCase):
    def _write(self, directory: str, name: str, content: str) -> str:
        path = Path(directory) / name
        path.write_text(content, encoding="utf-8")
        return str(path)

    def test_exit_zero_on_identical_and_one_on_divergence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ref = self._write(tmp, "ref.trace", _trace(SAMPLE_A, SAMPLE_B))
            same = self._write(tmp, "same.trace", _trace(SAMPLE_A, SAMPLE_B))
            mutated = self._write(
                tmp, "mut.trace", _trace(SAMPLE_A, SAMPLE_B.replace("pc=0302", "pc=0304"))
            )
            self.assertEqual(trace_diff.main([ref, same]), 0)
            self.assertEqual(trace_diff.main([ref, mutated]), 1)

    def test_exit_two_on_missing_file(self) -> None:
        self.assertEqual(trace_diff.main(["/nonexistent/a", "/nonexistent/b"]), 2)


if __name__ == "__main__":
    unittest.main()
