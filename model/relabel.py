#!/usr/bin/env python3
"""relabel.py - give one context of existing labels to another teacher (issue #1): the same states, a new answer.

Reads label files (gen_traces.py's {"state", "goal"} lines) in the order given and picks the pairs whose state
matches --hunger and (with --food-in-view) shows food. Two outputs, so nothing is lost or counted twice:

    python3 relabel.py --split IN... --kept K.jsonl                 # the pairs that do NOT match, unchanged
    TEACHER_API_KEY=... python3 relabel.py --relabel IN... --out R.jsonl --api openai --host URL --model M \\
        --label-seed 4701 [--shard 0/2]                              # the matching states, the new teacher's answers

The fold of K + all R shards then has the input's pairs, minus any state the teacher never answered (counted).
Seeds: each matching state gets gen_traces.label_seed(label_seed, its position among the matches, state), so
shards and reruns ask the same question with the same seed. A meta line goes to <out>.meta.jsonl.
"""
import argparse, json, os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_traces as gt  # noqa: E402


def matches(state, lo, hi, food):
    h = int(re.search(r"hunger (\d+)", state).group(1))
    return lo <= h <= hi and (not food or "food none" not in state)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("inputs", nargs="+")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--split", action="store_true", help="write the pairs that do not match to --kept")
    mode.add_argument("--relabel", action="store_true", help="ask the teacher for the matching states, write --out")
    ap.add_argument("--kept"); ap.add_argument("--out")
    ap.add_argument("--hunger", default="1-3", help="hunger range of the context (default 1-3)")
    ap.add_argument("--food-in-view", action="store_true", help="only states that show food (near, mid or far)")
    ap.add_argument("--api", choices=("ollama", "openai"), default="openai")
    ap.add_argument("--host"); ap.add_argument("--model")
    ap.add_argument("--temperature", type=float, default=gt.TEACHER_TEMPERATURE)
    ap.add_argument("--label-seed", type=int, default=None)
    ap.add_argument("--shard", default="0/1", help="k/n: this job asks every n-th matching state from the k-th")
    ap.add_argument("--timeout", type=float, default=60.0)
    a = ap.parse_args()
    gt.SCHEMA = 4
    lo, hi = (int(x) for x in a.hunger.split("-"))
    pairs = [json.loads(l) for f in a.inputs for l in open(f) if l.strip()]
    hit = [p for p in pairs if matches(p["state"], lo, hi, a.food_in_view)]
    if a.split:
        with open(a.kept, "w") as f:
            for p in pairs:
                if not matches(p["state"], lo, hi, a.food_in_view):
                    f.write(json.dumps(p) + "\n")
        print(f"{len(pairs)} pairs: {len(pairs) - len(hit)} kept -> {a.kept}, {len(hit)} to relabel")
        return
    k, n = (int(x) for x in a.shard.split("/"))
    mine = [(i, p) for i, p in enumerate(hit) if i % n == k]
    meta = dict(gt.teacher_meta(a.api, a.host, a.model, a.temperature, a.label_seed), inputs=[os.path.basename(x) for x in a.inputs],
                hunger=a.hunger, food_in_view=a.food_in_view, shard=a.shard, matches=len(hit), asked=len(mine),
                started=time.strftime("%Y-%m-%dT%H:%M:%S%z"))
    with open(a.out + ".meta.jsonl", "a") as mf:
        mf.write(json.dumps(meta) + "\n")
    done = failed = changed = 0
    with open(a.out, "w") as f:
        for i, p in mine:
            seed = gt.label_seed(a.label_seed, i, p["state"])
            goal = None
            for _ in range(3):
                try:
                    goal = gt.ask_teacher(a.api, a.host, a.model, p["state"], a.timeout, a.temperature, seed)
                    if goal: break
                except OSError as e:
                    print(f"[warn] {type(e).__name__}: {e}", file=sys.stderr)
            if not goal:
                failed += 1; continue
            f.write(json.dumps({"state": p["state"], "goal": goal}) + "\n"); f.flush()
            done += 1; changed += goal.split()[0] != p["goal"].split()[0]
            if done % 200 == 0:
                print(f"{done}/{len(mine)}", flush=True)
    print(f"done: {done} relabelled ({changed} changed goal), {failed} never answered -> {a.out}")


if __name__ == "__main__":
    main()
