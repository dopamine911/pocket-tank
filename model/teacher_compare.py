#!/usr/bin/env python3
"""Compare teacher runs of the same prompt_check panel. Stdlib only.

  python3 teacher_compare.py out/check-a.json out/check-b.json [more.json ...]

Each file is a `prompt_check.py --out` result. The runs must have asked the same questions (same
--schema, --n and --seed: the panel's states, in order); their teacher settings may differ (model,
temperature, label seed). Prints, for every pair of runs:

  same goal            share of questions both runs answered with the same goal
  same goal + urgency  the same, counting the urgency too
  per case             same-goal share per panel case

Two runs with the same teacher, temperature and --label-seed should agree on every question (the
labels repeat); the same teacher without a seed, or two seeds, measures how much the teacher agrees
with itself (upstream's docs/stats.md: 82% for gemma4:26b, "the practical ceiling").
"""
import argparse
import itertools
import json
import sys


def load(path):
    d = json.load(open(path))
    if "rows" not in d:
        sys.exit(f"{path}: not a prompt_check.py --out file")
    return d


def describe(d):
    return (f"{d.get('model')} T={d.get('temperature')} label_seed={d.get('label_seed')} "
            f"(panel seed {d.get('panel_seed')}, n {d.get('n')})")


def compare(a, b):
    """(same goal, same goal+urgency, answered by both, per case {case: (same, n)})"""
    ra, rb = a["rows"], b["rows"]
    if len(ra) != len(rb) or any(x["state"] != y["state"] or x["case"] != y["case"] for x, y in zip(ra, rb)):
        sys.exit("the runs did not ask the same questions (different --schema, --n or --seed)")
    same_g = same_gu = both = 0
    per = {}
    for x, y in zip(ra, rb):
        if not x["answer"] or not y["answer"]:
            continue
        both += 1
        g = x["answer"].split()[0] == y["answer"].split()[0]
        same_g += g
        same_gu += x["answer"] == y["answer"]
        s, n = per.get(x["case"], (0, 0))
        per[x["case"]] = (s + g, n + 1)
    return same_g, same_gu, both, per


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("runs", nargs="+", help="prompt_check.py --out files of the same panel")
    args = ap.parse_args()
    if len(args.runs) < 2:
        ap.error("give at least two runs")
    runs = [(p, load(p)) for p in args.runs]
    for p, d in runs:
        fails = sum(1 for r in d["rows"] if not r["answer"])
        print(f"{p}: {describe(d)}, {len(d['rows'])} questions, {fails} unanswered, prompt {d['prompt_sha256'][:12]}")
    for (pa, a), (pb, b) in itertools.combinations(runs, 2):
        g, gu, both, per = compare(a, b)
        print(f"\n{pa} vs {pb}: same goal {100 * g / both:.1f}% ({g}/{both}), "
              f"same goal + urgency {100 * gu / both:.1f}% ({gu}/{both})")
        print("  per case: " + ", ".join(f"{c} {100 * s / n:.0f}%" for c, (s, n) in per.items()))


if __name__ == "__main__":
    main()
