#!/bin/bash
# run_teacher_jobs.sh - teacher jobs, one after the other, on one OpenAI-compatible server (issue #1).
#
#   TEACHER_API_KEY=... HOST=http://localhost:8080/v1 MODEL=chat-teacher OUT=out/phase2 \
#     bash run_teacher_jobs.sh "panel 0.85 7" "panel 0.85 8" "gen 0.85 7 500 1"
#
# Jobs:
#   panel T LS            prompt_check.py --schema 4 (450 questions) at temperature T, label seed LS
#   gen T LS COUNT SIM    gen_traces.py --schema 4: COUNT labelled sim states from sim seed SIM
# One worker (WORKERS=1 default): with a label seed, a rerun on the same server type repeats every
# answer (450/450 measured 2026-11-09). Every job writes its result and a log under $OUT, named by
# model, temperature and seeds; a job whose result exists is skipped, so a rerun resumes.
set -uo pipefail
cd "$(dirname "$0")"
: "${HOST:?set HOST, the base URL of the server}" "${MODEL:?set MODEL}" "${OUT:?set OUT, a directory}"
WORKERS=${WORKERS:-1}
mkdir -p "$OUT"
log() { echo "[$(date '+%F %T')] $MODEL: $*" | tee -a "$OUT/jobs.log"; }
rc_all=0
for job in "$@"; do
    read -r kind t ls count sim <<<"$job"
    case "$kind" in
    panel)
        res="$OUT/panel-$MODEL-T$t-ls$ls.json"
        [ -s "$res" ] && { log "skip $job (done)"; continue; }
        log "start $job"
        python3 prompt_check.py --schema 4 --api openai --host "$HOST" --model "$MODEL" --workers "$WORKERS" \
            --temperature "$t" --label-seed "$ls" --out "$res.part" > "${res%.json}.log" 2>&1
        rc=$?
        ;;
    gen)
        res="$OUT/gen-$MODEL-T$t-ls$ls-sim$sim-n$count.jsonl"
        [ -s "$res" ] && { log "skip $job (done)"; continue; }
        log "start $job"
        rm -f "$res.part" "$res.part.meta.jsonl"
        python3 gen_traces.py --schema 4 --api openai --host "$HOST" --model "$MODEL" --temperature "$t" \
            --label-seed "$ls" --seed "$sim" --count "$count" --out "$res.part" > "${res%.jsonl}.log" 2>&1
        rc=$?
        [ $rc -eq 0 ] && mv "$res.part.meta.jsonl" "$res.meta.jsonl"
        ;;
    *) log "unknown job: $job"; rc_all=1; continue ;;
    esac
    if [ $rc -eq 0 ]; then mv "$res.part" "$res"; log "done $job ($(grep -c . "$res" 2>/dev/null || echo ?) lines)"
    else log "FAILED $job (rc $rc, see the log)"; rc_all=1; fi
done
exit $rc_all
