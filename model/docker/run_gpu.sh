#!/bin/bash
# run_gpu.sh - run one command in the ROCm training image on one GPU card (issue #1), from model/.
#
#   CARD=/dev/dri/renderD128 bash docker/run_gpu.sh python3 probe_fish.py --ckpt X --seed 11 --device cuda
#
# The same devices and groups harness.py gives its jobs; only the card named by CARD is visible
# (default renderD128). IMAGE defaults to pt-train-rocm:gfx120X (zaphod; marvin: pt-train-rocm:gfx1151).
set -euo pipefail
cd "$(dirname "$0")/.."
CARD=${CARD:-/dev/dri/renderD128}
IMAGE=${IMAGE:-pt-train-rocm:gfx120X}
exec docker run --rm -u "$(id -u):$(id -g)" \
    --device /dev/kfd --device "$CARD" \
    --group-add "$(getent group render | cut -d: -f3)" --group-add "$(getent group video | cut -d: -f3)" \
    --security-opt seccomp=unconfined \
    -v "$(cd .. && pwd)":/w -w /w/model "$IMAGE" "$@"
