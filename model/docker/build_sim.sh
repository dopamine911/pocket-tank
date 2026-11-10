#!/bin/bash
# build_sim.sh - inside pt-sim (Dockerfile.sim), from the repo root: build sim/fishsim and model/runq4.
set -euo pipefail
[ -e sim/lvgl ] || ln -s /opt/lvgl sim/lvgl          # sim/lvgl is git-ignored; README clones it there
make -C sim -j"$(nproc)" fishsim
cc -O3 -o model/runq4 model/runq4.c -lm
ls -l sim/fishsim model/runq4
