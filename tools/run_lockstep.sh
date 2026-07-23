#!/bin/sh
# ============================================================================
# CPU-only lockstep comparison: pyjr100emu (reference) vs Verilator MB8861.
#
# Usage: tools/run_lockstep.sh <program.prg> [cycles]
#   program.prg is resolved relative to the pyjr100emu checkout
#   (JR100EMU_PATH, default ../jr100emu), e.g. datas/maze_init_test.prg
#
# SPDX-License-Identifier: GPL-2.0-or-later
# ============================================================================
set -eu

REPO=$(cd "$(dirname "$0")/.." && pwd)
EMU=${JR100EMU_PATH:-$REPO/../jr100emu}
PROG=${1:?usage: run_lockstep.sh <program.prg> [cycles]}
CYCLES=${2:-100000}
WORK=${LOCKSTEP_WORK:-$REPO/sim/work}
NAME=$(basename "$PROG" .prg)

mkdir -p "$WORK"

# Reference run (exit code 2 = cycle limit reached, which is expected here)
set +e
( cd "$EMU" && PYTHONPATH=src .venv/bin/python -m jr100emu.debug_runner \
    --program "$PROG" --start 0x0300 --cycles "$CYCLES" --clear-regs \
    --save-initial-memory "$WORK/$NAME.img" \
    --trace "$WORK/$NAME.ref.trace" \
    --dump "$WORK/$NAME.ref.dump" --dump-range 0000:07FF ) 2>/dev/null
rc=$?
set -e
if [ "$rc" != 0 ] && [ "$rc" != 2 ]; then
    echo "error: reference run failed (exit $rc)" >&2
    exit "$rc"
fi

${MAKE:-make} -C "$REPO/sim" >/dev/null

"$REPO/sim/obj_dir/Vmb8861" \
    --image "$WORK/$NAME.img" --pc 0300 --sp 0244 --cycles "$CYCLES" \
    --trace "$WORK/$NAME.dut.trace" \
    --dump "$WORK/$NAME.dut.dump" --dump-range 0000:07FF \
    --program-name "$NAME.prg"

exec python3 "$REPO/tools/trace_diff.py" \
    "$WORK/$NAME.ref.trace" "$WORK/$NAME.dut.trace" --cpu-only \
    --mem "$WORK/$NAME.ref.dump" "$WORK/$NAME.dut.dump"
