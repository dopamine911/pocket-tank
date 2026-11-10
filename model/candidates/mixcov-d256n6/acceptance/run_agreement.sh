#!/bin/bash
# teacher agreement (docs/retrain-v4.md acceptance 1) with one teacher: $1 = server model name, then "q4path name" pairs
cd ~/pocket-tank
teacher=$1; shift
export TEACHER_API_KEY=$(grep -o 'ZAPHOD_KEY=.*' ~/llama-swap/.env | cut -d= -f2)
for m in "$@"; do
  read -r q4 name <<<"$m"
  docker run --rm --network host -e TEACHER_API_KEY -u $(id -u):$(id -g) -v $PWD:/w -w /w/model pt-sim:1 \
    python3 eval.py --schema 4 --count 300 --seed 1 --teacher --api openai --host http://127.0.0.1:8080/v1 \
    --model "$teacher" --label-seed 7 --run-bin ./runq4 --model-bin "${q4#model/}" --tok-bin out/tokenizer.bin \
    > model/out/acceptance/agree-$teacher-$name.txt 2>&1
  echo "$(date +%T) $teacher $name exit $?" >> model/out/acceptance/agree.log
done
