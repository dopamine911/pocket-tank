#!/usr/bin/env python3
"""devtest_score.py - score checkpoints on the device's own states (issue #1): the states pendant logs asked about,
labelled by each teacher (relabel.py --relabel --hunger 0-9). The model's greedy goal (top of its goal-token
softmax) against each teacher's label; the mean over the teachers is the yardstick.

    CARD=/dev/dri/renderD128 bash docker/run_gpu.sh python3 devtest_score.py --device cuda \\
        --teacher 26b=out/devtest/pendant-26b.jsonl --teacher 31b=out/devtest/pendant-31b.jsonl A.pt B.pt
"""
import argparse, json, os, sys
os.environ.setdefault("POCKET_SCHEMA", "4")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from student import Student  # noqa: E402

ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument("ckpt", nargs="+")
ap.add_argument("--teacher", action="append", required=True, help="NAME=labels.jsonl (state + goal per line)")
ap.add_argument("--device", default="cpu")
a = ap.parse_args()
T = []
for spec in a.teacher:
    name, path = spec.split("=", 1)
    T.append((name, {json.loads(l)["state"]: json.loads(l)["goal"].split()[0] for l in open(path) if l.strip()}))
states = sorted(set.intersection(*(set(lab) for _, lab in T)))
print(f"{len(states)} states labelled by every teacher; teachers agree with each other on "
      f"{sum(len({lab[s] for _, lab in T}) == 1 for s in states) / len(states):.1%}")
for ck in a.ckpt:
    d = Student(ck, device=a.device).dists(states)
    top = [max(p, key=p.get) for p, _ in d]
    scores = [sum(g == lab[s] for g, s in zip(top, states)) / len(states) for _, lab in T]
    both = [(g, s) for g, s in zip(top, states) if len({lab[s] for _, lab in T}) == 1]   # the teachers agree here
    cons = sum(g == T[0][1][s] for g, s in both) / max(len(both), 1)
    print(f"{ck}: " + "  ".join(f"{n} {sc:.1%}" for (n, _), sc in zip(T, scores)) + f"  | mean {sum(scores) / len(scores):.1%}"
          f"  | where the teachers agree ({len(both)}): {cons:.1%}")
