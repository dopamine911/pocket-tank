#!/bin/bash
# run_sweep.sh - harness runs one after the other (issue #1, the size sweep).
#
#   bash run_sweep.sh fish-14m-all fish-14m-decision ...          # these runs, in this order
#   SWEEP_LOG=out/sweep-a.log bash run_sweep.sh ...                # two drivers side by side: one log each
#
# Each run spreads its seeds one per free card (harness.py). Two drivers can run at once: a card
# with a harness job is busy for the other driver (harness.py checks its containers), so no card
# ever takes two jobs. A run with a report.json is skipped (rerunning continues); a failed run is
# logged and the driver goes on. SWEEP_MODE=opportunistic shares the cards with served models;
# the default is the run's own mode ("training": the lab's training profile on every host).
set -uo pipefail
cd "$(dirname "$0")"
LOG=${SWEEP_LOG:-out/sweep.log}
mkdir -p "$(dirname "$LOG")"
log() { echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }
failed=""
for run in "$@"; do
    if [ -f "out/harness/$run/report.json" ]; then
        log "$run: report exists, skipped"
        continue
    fi
    log "$run: starting"
    if python3 harness.py run "$run" --poll 20 ${SWEEP_MODE:+--mode "$SWEEP_MODE"} >> "$LOG" 2>&1; then
        log "$run: done"
    else
        log "$run: FAILED (rc $?); see above and out/harness/$run/"
        failed="$failed $run"
    fi
done
log "driver finished${failed:+; FAILED:$failed}"
[ -z "$failed" ]
