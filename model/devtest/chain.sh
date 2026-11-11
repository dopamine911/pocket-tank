#!/bin/bash
# after the three label jobs: relabel the 31B's fed eating, train fish-d256-n6-decision-csim, run the rule's checks (issue #1)
cd ~/pocket-tank/model; C=out/cstates
until [ "$(cat $C/label.done 2>/dev/null | grep -c exit)" -ge 4 ]; do sleep 30; done
cat $C/label.done; grep -h '^done:' $C/lab-*.log
python3 relabel.py --split $C/lab-31b-a.jsonl $C/lab-31b-b1.jsonl $C/lab-31b-b2.jsonl --kept $C/kept-31b.jsonl --hunger 1-3 --food-in-view
export TEACHER_API_KEY=$(grep -o '^ZAPHOD_KEY=.*' ~/llama-swap/.env | cut -d= -f2)
for k in 0 1; do m=chat-teacher-26b; [ $k = 1 ] && m=chat-teacher-26b-c1
  python3 relabel.py --relabel $C/lab-31b-a.jsonl $C/lab-31b-b1.jsonl $C/lab-31b-b2.jsonl --out $C/relabel26b-31b-s${k}of2.jsonl --hunger 1-3 --food-in-view \
    --api openai --host http://127.0.0.1:8080/v1 --model $m --label-seed 6004 --shard $k/2 > $C/relabel-s$k.log 2>&1 &
done; wait
grep -h '^done:' $C/relabel-s*.log
echo "pairs: 26B $(wc -l < $C/lab-26b.jsonl) + kept $(wc -l < $C/kept-31b.jsonl) + relabelled $(cat $C/relabel26b-31b-s?of2.jsonl | wc -l)"
lab training-mode on 2>&1 | tail -1
SWEEP_LOG=out/sweep-csim.log bash run_sweep.sh fish-d256-n6-decision-csim; rc=$?
lab training-mode off 2>&1 | tail -1
[ $rc -eq 0 ] || { echo "run FAILED rc $rc"; exit 1; }
H=out/harness/fish-d256-n6-decision-csim
grep 'pairs, sha256' out/sweep-csim.log | head -1
sed -n '/## Rows by seed/,/smallest scaled/p' $H/report.md | grep -E 'F1 |F3 |F4 |F5 |F10|F13|F14|smallest'
grep 'Selected' $H/report.md
G="bash docker/run_gpu.sh python3"
$G devtest_score.py --device cuda --teacher 26b=out/devtest/pendant-26b.jsonl --teacher 31b=out/devtest/pendant-31b.jsonl \
   out/q4probe/stock-q4.pt out/q4probe/bigplay-s1-q4.pt out/q4probe/relabel-s1-q4.pt $H/s{1,2,3}/ckpt.pt 2>&1 | grep -v Warning
$G dart_by_hunger.py --device cuda $H/s{1,2,3}/ckpt.pt 2>&1 | grep -v Warning
$G eat_by_hunger.py --device cuda out/q4probe/relabel-s1-q4.pt $H/s{1,2,3}/ckpt.pt 2>&1 | grep -v Warning
for s in 1 2 3; do echo "s$s p37: $($G probe_fish.py --ckpt $H/s$s/ckpt.pt --seed 37 --device cuda --out $H/s$s/probe_p37_n400.json 2>&1 | grep -E 'FAIL| F3 | F4 | F14 ' | sed 's/  */ /g' | tr '\n' ' ')"; done
$G pendant_replay.py out/dartcheck/states-pendant-all.txt out/q4probe/relabel-s1-q4.pt $H/s{1,2,3}/ckpt.pt 2>&1 | grep -v -E 'Warning|grep "advisor'
