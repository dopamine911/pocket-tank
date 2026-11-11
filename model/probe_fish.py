#!/usr/bin/env python3
"""Probe a trained fish (schema v4) student on prompt_check.py's v4 rows F1-F14: the trained model's
side of the checks (prompt_check.py scores the teacher with the same table on the same states).

  cd model
  POCKET_SCHEMA=4 .venv/bin/python probe_fish.py --ckpt out/ckpt.pt          # the table, out/probe_fish_ckpt.json
  POCKET_SCHEMA=4 python3 probe_fish.py --ckpt ... --device cuda             # on a GPU (harness.py's jobs)
  python3 probe_fish.py --selftest                                           # the arithmetic on a fake model (no torch)

States: prompt_check.panel(rng, 4, --n, extra=True): upstream's v4 panel plus the extra cases (fedfood),
at --n 400 by default (10x the teacher's 40: a student costs no teacher calls, and 400 per case keeps a
row's sampling noise near +-0.02). Each line is read as the device reads it (student.Student): a
softmax over the fish's eight goal tokens at temperature 1.0, so a row's value is the EXPECTED rate of
the device's sampled decisions. F12 (flee anywhere, <= 0.001) is the student's leak onto flee_shadow,
which no v4 label uses. F14 is a report row (no bar).

From dopamine911/pocket-terrarium model/probe_fish.py (branch feat/fish-size-sweep), reviewed (issue #1):
dart | bold 9 is a check again at upstream's bar, the fedfood case is added, n is 400 by default. The
JSON keeps that shape (rows: row, value, n, threshold, result; passed) so harness.py reads it unchanged.
"""
import argparse
import json
import os
import random
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_traces as gt  # noqa: E402
import prompt_check as pc  # noqa: E402
import train_tokenizer as tok  # noqa: E402

SCHEMA = 4


def goals():
    """the device's goal tokens for the fish: all eight (gt.GOALS), not the seven the v4 labels use"""
    return list(gt.GOALS)


def probe(dists, n, seed):
    """the v4 panel (with the extra cases) through `dists` (lines -> [(distribution, goal mass)]);
    returns (rows, by, goal masses)"""
    gt.SCHEMA = SCHEMA
    panel = pc.panel(random.Random(seed), SCHEMA, n, extra=True)
    by, masses = {}, []
    for (case, st), (d, m) in zip(panel, dists([st for _, st in panel])):
        by.setdefault(case, []).append((st, d))
        masses.append(m)
    return pc.v4_table(by), by, masses


def label(row):
    return row.split()[0]


def print_table(rows):
    print(f"  {'row':56s} {'value':>6s}  {'threshold':10s} result")
    for name, v, n, want, ok in rows:
        result = "report" if ok is None else "PASS" if ok else "FAIL"
        print(f"  {name.strip():56s} {v:6.3f}  {want:10s} {result:6s} (n={n})")


def report(rows, by, masses, extra):
    """the JSON the table came from"""
    return dict(extra, rows=[{"row": name.strip(), "value": v, "n": n, "threshold": want,
                              "result": "report" if ok is None else "PASS" if ok else "FAIL"}
                             for name, v, n, want, ok in rows],
                goal_mass={"mean": sum(masses) / len(masses), "min": min(masses)},
                cases={c: {"n": len(by[c]), "mean": pc.mean_dist(by, c)} for c in pc.V4_CASE_ORDER if c in by},
                passed=all(ok for *_, ok in rows if ok is not None))


def selftest():
    """the arithmetic on a hand-made fake model: known distributions per case give known rows"""
    gs = goals()

    def mk(**kw):
        kw = dict(kw, flee_shadow=0.0)        # the unused token: a trained student gives it ~nothing
        rest = (1.0 - sum(kw.values())) / (len(gs) - len(kw))
        return {g: kw.get(g, rest) for g in gs}
    fake = {"social9": mk(follow_friend=0.8), "social1": mk(follow_friend=0.02), "bold9": mk(dart_play=0.04),
            "bold1": mk(dart_play=0.05),                                  # over F4's 0.03: FAIL
            "content": mk(explore=0.44, rest=0.2), "lonely": mk(seek_food=0.02), "starving": mk(seek_food=0.97),
            "trust9": mk(rest=0.3), "trust0": mk(explore=0.3),
            "bored9bub": mk(visit_bubbles=0.1, explore=0.5), "bored9fol": mk(follow_friend=0.3),   # F9 0.3 > 0.15: FAIL
            "bored0bub": mk(visit_bubbles=0.6), "nightbored": mk(rest=0.9), "fedfood": mk(seek_food=0.3)}
    gt.SCHEMA = SCHEMA
    panel = pc.panel(random.Random(11), SCHEMA, 40, extra=True)
    case_of = {}
    for case, st in panel:
        case_of.setdefault(st, case)
    rows, by, masses = probe(lambda lines: [(fake[case_of[line]], 1.0) for line in lines], 40, 11)
    want = {"F1": (0.8, True), "F2": (0.02, True), "F3": (0.04, False), "F4": (0.05, False), "F5": (0.97, True),
            "F6": (0.02, True), "F7": (0.1, True), "F8": (0.5, True), "F9": (0.3, False), "F10": (0.6, True),
            "F11": (0.9, True), "F12": (0.0, True), "F13": (0.44, True), "F14": (0.3, None)}
    seen = set()
    for name, v, n, w, ok in rows:
        k = label(name)
        assert k in want and k not in seen, (k, name)
        seen.add(k)
        assert abs(v - want[k][0]) < 1e-9 and ok == want[k][1], (k, v, ok, want[k])
    assert seen == set(want) and masses == [1.0] * len(panel) and len(gs) == 8
    leak = pc.v4_table({"content": [("s", dict(mk(explore=0.4), flee_shadow=0.01))]})   # a leak onto flee_shadow fails F12
    assert [r[4] for r in leak if label(r[0]) == "F12"] == [False]
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "probe.json")
        with open(path, "w") as fh:
            json.dump(report(rows, by, masses, {"ckpt": "fake"}), fh)
        back = json.load(open(path))
    assert back["passed"] is False and [r["result"] for r in back["rows"]].count("FAIL") == 3
    print_table(rows)
    print(f"\nselftest OK: {len(rows)} rows on {len(panel)} states match the hand-made distributions "
          f"(F3 0.04, F4 0.05 and F9 0.30 FAIL as built, F14 report-only, F12 0.00)")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ckpt", help="train.py's checkpoint (POCKET_SCHEMA=4)")
    ap.add_argument("--n", type=int, default=400, help="prompt_check's --n: states per major case (default 400)")
    ap.add_argument("--seed", type=int, default=11, help="prompt_check's panel seed")
    ap.add_argument("--temp", type=float, default=1.0, help="sampling temperature (the device: 1.0)")
    ap.add_argument("--out", default=None, help="the JSON (default out/probe_fish_<checkpoint name>.json)")
    ap.add_argument("--strict", action="store_true", help="exit 1 if a row fails")
    ap.add_argument("--device", default="cpu", help="cpu|cuda: where the checkpoint runs")
    ap.add_argument("--selftest", action="store_true", help="check the arithmetic on a fake model and stop")
    args = ap.parse_args()
    tok.set_schema(SCHEMA)
    if args.selftest:
        selftest()
        return
    if not args.ckpt:
        ap.error("--ckpt is required (or --selftest)")
    if args.temp <= 0:
        ap.error("--temp must be > 0 (the device samples at 1.0)")
    import student
    s = student.Student(args.ckpt, args.temp, args.device, goals=goals(), name="fish v4")
    rows, by, masses = probe(s.dists, args.n, args.seed)
    print(f"{args.ckpt}: iter {s.info['iter']}, val_loss {s.info['val_loss']}, goal_nll {s.info['goal_nll']}; "
          f"{sum(len(v) for v in by.values())} states (v4 panel + extra cases, --n {args.n}, seed {args.seed}), "
          f"temperature {args.temp}; goal-token mass mean {sum(masses) / len(masses):.3f}, min {min(masses):.3f}\n")
    print_table(rows)
    out = args.out or os.path.join(HERE, "out", f"probe_fish_{os.path.splitext(os.path.basename(args.ckpt))[0]}.json")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    rep = report(rows, by, masses, {"ckpt": args.ckpt, "checkpoint": s.info, "n": args.n, "seed": args.seed,
                                    "temperature": args.temp})
    with open(out, "w") as fh:
        json.dump(rep, fh, indent=1)
    failed = [label(r["row"]) for r in rep["rows"] if r["result"] == "FAIL"]
    print(f"\n{'all rows PASS' if rep['passed'] else 'FAIL: ' + ', '.join(failed)}\n-> {out}")
    if args.strict and not rep["passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
