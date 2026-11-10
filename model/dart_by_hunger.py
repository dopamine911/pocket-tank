#!/usr/bin/env python3
"""dart_by_hunger.py - P(dart) on prompt_check's bold 9 / bold 1 cases with hunger pinned to 0, 1 and 2 (issue #1).

The panel draws the bold cases' hunger once per panel seed (panel 11: 0, 23: 2, 37: 1), so F3 / F4 on one
panel see one hunger value. This measures all three, n=400 each, for any number of checkpoints
(train.py's, or q4_to_ckpt.py's from a model_q4.bin):

    CARD=/dev/dri/renderD128 bash docker/run_gpu.sh python3 dart_by_hunger.py --device cuda out/a.pt out/b.pt
"""
import argparse, os, random, sys
os.environ.setdefault("POCKET_SCHEMA", "4")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import prompt_check as pc  # noqa: E402
from student import Student  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("ckpt", nargs="+")
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--device", default="cpu")
    a = ap.parse_args()
    for ck in a.ckpt:
        st = Student(ck, device=a.device)
        row = []
        for bold in (9, 1):
            for h in (0, 1, 2):
                rng = random.Random(100 + h)
                lines = [pc.state(rng, 4, bold=bold, energy=9, hunger=h) for _ in range(a.n)]
                row.append(f"bold{bold} h{h} {sum(d['dart_play'] for d, _ in st.dists(lines)) / a.n:.3f}")
        print(ck, " | ".join(row))


if __name__ == "__main__":
    main()
