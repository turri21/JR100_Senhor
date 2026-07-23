#!/bin/sh
# ============================================================================
# Compile the MiSTer .rbf in a Quartus 17.0 container.
#
# The project sources are copied to the container-local filesystem before
# compiling: Quartus performs heavy small-file I/O in db/, which is
# pathologically slow over a bind mount (measured on Apple Container /
# virtiofs). Only output_files/ is copied back to the repository.
#
# Runtime-neutral: the same image and command are used locally and in CI.
#   CONTAINER_RUNTIME  container (default, Apple Container + Rosetta) |
#                      podman | docker
#   QUARTUS_IMAGE      override the Quartus image (default raetro/quartus:17.0)
#
# Usage: tools/compile_rbf.sh [revision]   (default: JR100)
# Output: output_files/<revision>.rbf
#
# SPDX-License-Identifier: GPL-2.0-or-later
# ============================================================================
set -eu

REPO=$(cd "$(dirname "$0")/.." && pwd)
RUNTIME=${CONTAINER_RUNTIME:-container}
IMAGE=${QUARTUS_IMAGE:-docker.io/raetro/quartus:17.0}
REVISION=${1:-JR100}

BUILD_CMD='
set -e
mkdir -p /work
cp /src/*.qpf /src/*.qsf /src/*.sdc /src/*.srf /src/*.sv /src/files.qip /work/
cp -a /src/rtl /src/sys /work/
cd /work
quartus_sh --flow compile "$1"
mkdir -p /src/output_files
cp -a /work/output_files/. /src/output_files/
'

echo "compile_rbf: runtime=$RUNTIME image=$IMAGE revision=$REVISION"

case "$RUNTIME" in
    container)
        exec container run --rm --arch amd64 \
            --cpus "${QUARTUS_CPUS:-8}" --memory "${QUARTUS_MEMORY:-8g}" \
            --volume "$REPO:/src" \
            "$IMAGE" sh -c "$BUILD_CMD" build "$REVISION"
        ;;
    podman|docker)
        exec "$RUNTIME" run --rm --platform linux/amd64 \
            -v "$REPO:/src" \
            "$IMAGE" sh -c "$BUILD_CMD" build "$REVISION"
        ;;
    *)
        echo "error: unknown CONTAINER_RUNTIME '$RUNTIME'" >&2
        exit 2
        ;;
esac
