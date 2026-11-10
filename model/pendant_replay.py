"""pendant_replay.py - replay the states pendant logs asked about through checkpoints: mean P(dart) for timid (bold 0-3) and bold (7-9) fish, and P(seek_food) for fed fish (hunger 0-3) with food in view (issue #1).
   grep "advisor: zone " LOG | sed -E "s/^I \([0-9]+\) advisor: //; s/ -> .*//" > states.txt
   CARD=/dev/dri/renderD128 bash docker/run_gpu.sh python3 pendant_replay.py states.txt[,more.txt] A.pt B.pt"""
import os, sys, re
os.environ["POCKET_SCHEMA"] = "4"; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from student import Student
v = lambda s, k: int(re.search(k + r" (\d+)", s).group(1))
S = []
for f in sys.argv[1].split(","):
    S += [l.strip() for l in open(f) if l.strip()]
T = [s for s in S if v(s, "bold") <= 3]; B = [s for s in S if v(s, "bold") >= 7]
F = [s for s in S if v(s, "hunger") <= 3 and "food none" not in s]
print(len(S), "pendant states;", len(T), "timid,", len(B), "bold,", len(F), "fed with food in view")
for ck in sys.argv[2:]:
    st = Student(ck, device="cuda")
    pt = [p["dart_play"] for p, _ in st.dists(T)]; pb = [p["dart_play"] for p, _ in st.dists(B)]
    pf = [p["seek_food"] for p, _ in st.dists(F)]
    print(f"{ck.split('/')[-1]}: timid mean {sum(pt)/len(pt):.3f} (states > 0.05: {sum(x > 0.05 for x in pt)}) | bold mean {sum(pb)/len(pb):.3f}"
          f" | fed, food in view: seek_food {sum(pf)/len(pf):.3f}")
