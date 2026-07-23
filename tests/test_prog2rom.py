"""Tests for tools/prog2rom.py (PROG container -> raw 8 KiB image)."""

from __future__ import annotations

import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TOOL = REPO / "tools" / "prog2rom.py"


def make_prog(payload: bytes, *, name: bytes = b"TESTROM", start: int = 0xE000) -> bytes:
    return (
        b"PROG"
        + struct.pack("<I", 1)                 # version
        + struct.pack("<I", len(name)) + name
        + struct.pack("<I", start)
        + struct.pack("<I", len(payload))
        + struct.pack("<I", 0)                 # reserved
        + payload
    )


class Prog2RomTest(unittest.TestCase):
    def run_tool(self, prog: bytes, tmp: str):
        src = Path(tmp) / "rom.prg"
        out = Path(tmp) / "boot.rom"
        src.write_bytes(prog)
        result = subprocess.run(
            [sys.executable, str(TOOL), str(src), str(out)],
            capture_output=True, text=True,
        )
        return result, out

    def test_extracts_payload_padded_to_8k(self) -> None:
        payload = bytes(range(256)) * 8      # 2 KiB pattern
        with tempfile.TemporaryDirectory() as tmp:
            result, out = self.run_tool(make_prog(payload), tmp)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = out.read_bytes()
            self.assertEqual(len(data), 0x2000)
            self.assertEqual(data[: len(payload)], payload)
            self.assertEqual(data[len(payload):], bytes(0x2000 - len(payload)))

    def test_rejects_non_prog_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result, out = self.run_tool(b"NOTPROG" + bytes(64), tmp)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
