#!/usr/bin/env python3
"""eat_by_hunger.py - P(seek_food) with food near at hunger 0-8 (prompt_check's base state, n=400 per value), per
checkpoint (issue #1): eating when not hungry (hunger 1-3) should fall without losing eating when hungry (4-8).
    CARD=/dev/dri/renderD128 bash docker/run_gpu.sh python3 eat_by_hunger.py --device cuda A.pt B.pt"""
import argparse, os, random, sys
os.environ.setdefault("POCKET_SCHEMA", "4")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prompt_check as pc  # noqa: E402
from student import Student  # noqa: E402

ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument("ckpt", nargs="+"); ap.add_argument("--n", type=int, default=400); ap.add_argument("--device", default="cpu")
a = ap.parse_args()
for ck in a.ckpt:
    st = Student(ck, device=a.device); row = []
    for h in range(9):
        rng = random.Random(200 + h)
        lines = [pc.state(rng, 4, hunger=h, food=f"near {rng.randint(1, 12)}") for _ in range(a.n)]
        row.append(f"h{h} {sum(d['seek_food'] for d, _ in st.dists(lines)) / a.n:.2f}")
    print(ck, " ".join(row))
