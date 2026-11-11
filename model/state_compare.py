#!/usr/bin/env python3
"""state_compare.py - compare the state lines of several sources field by field (issue #1: does the training
generator make the states the device sees?).

Each source is NAME=FILE[,FILE...]: plain text (one state line per line: pendant logs' states, sim/fishsim-round
POCKET_DUMP_STATES dumps) or jsonl with a "state" field (gen_traces.py labels). For every field: each source's
share of each value, and the total-variation distance of every source from the first (0 = same, 1 = disjoint).

    python3 state_compare.py pendant=states.txt csim=dump1.txt,dump2.txt python=gen-*.jsonl
"""
import collections, glob, json, sys

FIELDS = ("zone", "hunger", "energy", "stress", "curiosity", "bold", "social", "stage", "trust", "bored",
          "food", "friend", "bubble", "reef", "wall", "last", "time")
SIGHTED = ("food", "friend", "bubble", "reef", "wall")


def fields(s):
    t, d, i = s.split(), {}, 0
    while i < len(t):
        k = t[i]
        if k in SIGHTED and i + 1 < len(t) and t[i + 1] not in ("none", "clear"):
            d[k] = t[i + 1]; i += 3            # "near 5": the bucket, the clock direction skipped
        else:
            d[k] = t[i + 1] if i + 1 < len(t) else "?"; i += 2
    return d


def load(spec):
    out = []
    for pat in spec.split(","):
        for f in sorted(glob.glob(pat)) or [pat]:
            for line in open(f):
                line = line.strip()
                if line:
                    out.append(fields(json.loads(line)["state"] if line.startswith("{") else line))
    return out


def main():
    srcs = [(a.split("=", 1)[0], load(a.split("=", 1)[1])) for a in sys.argv[1:]]
    print(" | ".join(f"{n} {len(x)} states" for n, x in srcs))
    names = [n for n, _ in srcs]
    print(f"{'field':9s} TV vs {names[0]}: " + " ".join(f"{n}" for n in names[1:]) + "   | shares % (" + " / ".join(names) + ")")
    for k in FIELDS:
        dists = []
        for _, X in srcs:
            c = collections.Counter(x.get(k, "-") for x in X)
            dists.append({v: c[v] / len(X) for v in c})
        keys = sorted(set().union(*dists), key=lambda v: (len(v), v))
        tvs = [0.5 * sum(abs(dists[0].get(v, 0) - d.get(v, 0)) for v in keys) for d in dists[1:]]
        shares = "  ".join(f"{v}:" + "/".join(f"{100 * d.get(v, 0):.0f}" for d in dists) for v in keys)
        print(f"{k:9s} " + " ".join(f"{t:.2f}" for t in tvs) + "   | " + shares)


if __name__ == "__main__":
    main()
