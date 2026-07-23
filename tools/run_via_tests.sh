#!/bin/sh
# Run per-cycle VIA unit scenarios: pyjr100emu golden vs Verilator DUT.
# SPDX-License-Identifier: GPL-2.0-or-later
set -eu
REPO=$(cd "$(dirname "$0")/.." && pwd)
WORK=${LOCKSTEP_WORK:-$REPO/sim/work}
mkdir -p "$WORK"
${MAKE:-make} -C "$REPO/sim" obj_dir/Vjr100_via >/dev/null
fail=0
for scn in "$REPO"/tests/via/*.scn; do
    name=$(basename "$scn" .scn)
    python3 "$REPO/tools/gen_via_vectors.py" --scenario "$scn" --out "$WORK/$name.golden"
    "$REPO/sim/obj_dir/Vjr100_via" --scenario "$scn" --out "$WORK/$name.dut"
    if /usr/bin/diff -q "$WORK/$name.golden" "$WORK/$name.dut" >/dev/null; then
        echo "PASS $name"
    else
        echo "FAIL $name"
        /usr/bin/diff "$WORK/$name.golden" "$WORK/$name.dut" | head -8
        fail=1
    fi
done
exit $fail
