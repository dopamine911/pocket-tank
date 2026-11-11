#!/bin/bash
# label one part with one teacher, after an optional wait for a tmux session to end: $1 part, $2 out, $3 host, $4 model, $5 key var, $6 label seed, $7 wait-for session
cd ~/pocket-tank/model
[ -n "${7:-}" ] && while tmux has-session -t "$7" 2>/dev/null; do sleep 10; done
export TEACHER_API_KEY=$(grep -o "^$5=.*" ~/llama-swap/.env | cut -d= -f2)
python3 relabel.py --relabel "$1" --out "$2" --hunger 0-9 --api openai --host "$3" --model "$4" --label-seed "$6" > "${2%.jsonl}.log" 2>&1
echo "$(date +%T) $2 exit $?" >> out/cstates/label.done
