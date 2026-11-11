#!/usr/bin/env python3
"""Label mix of teacher traces (gen_traces.py output), side by side. Stdlib only.

  python3 label_mix.py out/a.jsonl out/b.jsonl [...]

For each file: the goal shares, and P(seek_food) by hunger with food in view and without (the
generator puts food in view in most states, so a teacher that eats at low hunger skews the whole
dataset towards seek_food - the 31B's known skew, issue #1). With several files from the same sim
seed (the same states), also the share of states on which each file agrees with the first.
"""
import argparse
import json
import sys


def load(path):
    rows = []
    for line in open(path):
        line = line.strip()
        if line:
            d = json.loads(line)
            rows.append((d["state"], d["goal"].split()[0]))
    return rows


def field(state, name):
    w = state.split()
    for i, x in enumerate(w[:-1]):
        if x == name:
            return w[i + 1]
    return None


def mix(rows):
    out = {}
    for _, g in rows:
        out[g] = out.get(g, 0) + 1
    return {g: c / len(rows) for g, c in sorted(out.items(), key=lambda kv: -kv[1])}


def eat_by_hunger(rows, food_in_view):
    """{hunger bucket: (P(seek_food), n)} for states with/without food in view"""
    buckets = {"0-2": range(0, 3), "3-4": range(3, 5), "5-6": range(5, 7), "7-9": range(7, 10)}
    out = {}
    for name, rng in buckets.items():
        sel = [g for s, g in rows if int(field(s, "hunger")) in rng and (field(s, "food") != "none") == food_in_view]
        out[name] = (sum(g == "seek_food" for g in sel) / len(sel) if sel else float("nan"), len(sel))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("files", nargs="+")
    args = ap.parse_args()
    runs = [(p, load(p)) for p in args.files]
    goals = sorted({g for _, r in runs for _, g in r})
    w = max(len(p.split("/")[-1]) for p, _ in runs)
    print(f"{'file':{w}s}  {'n':>5s}  " + "  ".join(f"{g[:11]:>11s}" for g in goals))
    for p, r in runs:
        m = mix(r)
        print(f"{p.split('/')[-1]:{w}s}  {len(r):5d}  " + "  ".join(f"{100 * m.get(g, 0):10.1f}%" for g in goals))
    for food in (True, False):
        print(f"\nP(seek_food) by hunger, food {'in view' if food else 'none'} (n per file):")
        for p, r in runs:
            e = eat_by_hunger(r, food)
            print(f"  {p.split('/')[-1]:{w}s}  " + "  ".join(f"hunger {k}: {v:.2f} (n={n})" for k, (v, n) in e.items()))
    share = sum(field(s, "food") != "none" for s, _ in runs[0][1]) / len(runs[0][1])
    print(f"\nfood in view in {100 * share:.0f}% of {args.files[0].split('/')[-1]}'s states")
    base = runs[0][1]
    for p, r in runs[1:]:
        if len(r) == len(base) and all(a[0] == b[0] for a, b in zip(base, r)):
            same = sum(a[1] == b[1] for a, b in zip(base, r))
            print(f"same states as the first file: {p.split('/')[-1]} agrees on {100 * same / len(r):.1f}% ({same}/{len(r)})")
        else:
            print(f"{p.split('/')[-1]}: not the same states as the first file (the sim follows the labels), no per-state agreement")
    return 0


if __name__ == "__main__":
    sys.exit(main())
