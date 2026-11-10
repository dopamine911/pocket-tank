"""dart_on_sim.py - P(dart) on the --play shards' bold 7+, rested, fed, no-food daytime sim states (wall near/mid), per checkpoint (issue #1).
   CARD=/dev/dri/renderD128 bash docker/run_gpu.sh python3 dart_on_sim.py A.pt B.pt"""
import os, sys, json, re, glob
os.environ["POCKET_SCHEMA"] = "4"; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from student import Student
v = lambda s, k: int(re.search(k + r" (\d+)", s).group(1))
S = []
for f in glob.glob("out/data/fish2*-play/gen-*play0.6.jsonl") + glob.glob("out/data/fish3*-play/gen-*play0.6.jsonl"):
    for l in open(f):
        s = json.loads(l)["state"]
        if v(s,"energy") >= 7 and v(s,"hunger") <= 3 and "food none" in s and "time day" in s and v(s,"bold") >= 7: S.append(s)
print(len(S), "states")
for ck in sys.argv[1:]:
    d = Student(ck, device="cuda").dists(S)
    by = {h: [p["dart_play"] for (p, _), s in zip(d, S) if v(s,"hunger") == h] for h in range(4)}
    print(f"{ck}: all {sum(p['dart_play'] for p, _ in d)/len(d):.3f} | " + " ".join(f"h{h} {sum(x)/len(x):.3f}" for h, x in by.items()))
