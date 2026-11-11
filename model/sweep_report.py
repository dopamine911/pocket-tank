#!/usr/bin/env python3
"""The size sweep's verdict by the rules fixed before it ran (issue #1, comment of 2026-11-09 21:35).

  python3 sweep_report.py --reference fish-14m-all fish-d256-n4-decision fish-d192-n4-all ... [--markdown out.md]

Reads out/harness/<run>/s<seed>/{manifest.json, probe_*.json} for each run (harness.py's outputs).
A row's value for a seed is the mean of that seed's probe panels.

Tier A (the answer): a run passes when, on every seed, every check row (rows with a bar; F14 and
other report rows are left out) is no worse than the reference's worst seed in the row's direction
(">=" rows: value >= the reference's lowest; "<=", "<" and "==" rows: value <= the reference's
highest), and the seed's goal NLL is no higher than the reference's highest. The smallest passing
run (by parameters) is the result.

Tier B (reported as-is): every row against its own bar (upstream's), per seed and panel.
"""
import argparse
import glob
import json
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out", "harness")
LIMIT_RE = re.compile(r"^\s*(>=|<=|==|>|<)\s*([-+]?(?:\d+\.?\d*|\.\d+))")


def key(row):
    return row.split()[0]


def load_run(run):
    """{seed: {"manifest": ..., "panels": [probe JSON, ...]}}"""
    seeds = {}
    for d in sorted(glob.glob(os.path.join(OUT, run, "s*"))):
        m = os.path.join(d, "manifest.json")
        if not os.path.exists(m):
            continue
        probes = [json.load(open(p)) for p in sorted(glob.glob(os.path.join(d, "probe_*.json")))]
        seeds[int(os.path.basename(d)[1:])] = {"manifest": json.load(open(m)), "panels": probes, "dir": d}
    return seeds


def row_values(seeds):
    """{row key: {"bar": threshold, "name": full name, seed: mean over panels}}"""
    out = {}
    for s, d in seeds.items():
        per = {}
        for p in d["panels"]:
            for r in p["rows"]:
                k = key(r["row"])
                e = out.setdefault(k, {"bar": r["threshold"], "name": r["row"]})
                per.setdefault(k, []).append(r["value"])
        for k, vals in per.items():
            out[k][s] = statistics.fmean(vals)
    return out


def direction(bar):
    m = LIMIT_RE.match(bar or "")
    if not m:
        return None
    return "up" if m[1] in (">=", ">") else "down"


def passes_bar(v, bar):
    m = LIMIT_RE.match(bar or "")
    if not m:
        return None
    op, x = m[1], float(m[2])
    return {">=": v >= x, ">": v > x, "<=": v <= x, "<": v < x, "==": v <= 0.001 if x == 0 else v == x}[op]


def tier_a(cand, ref):
    """(passed, [(seed, row, value, reference worst)] failures)"""
    rv, cv = row_values(ref), row_values(cand)
    fails = []
    ref_nll = max(d["manifest"]["train"]["goal_nll"] for d in ref.values())
    for s, d in cand.items():
        nll = d["manifest"]["train"]["goal_nll"]
        if nll > ref_nll:
            fails.append((s, "goal NLL", nll, ref_nll))
        for k, e in cv.items():
            dirn = direction(e["bar"])
            if dirn is None or k not in rv or s not in e:
                continue
            ref_vals = [v for sk, v in rv[k].items() if isinstance(sk, int)]
            worst = min(ref_vals) if dirn == "up" else max(ref_vals)
            ok = e[s] >= worst - 1e-9 if dirn == "up" else e[s] <= worst + 1e-9
            if not ok:
                fails.append((s, k, e[s], worst))
    return (not fails and len(cand) == len(ref)), fails


def tier_b(seeds):
    """[(seed, panel index, row, value, bar)] values that miss their own bar"""
    out = []
    for s, d in seeds.items():
        for i, p in enumerate(d["panels"]):
            for r in p["rows"]:
                ok = passes_bar(r["value"], r["threshold"])
                if ok is False:
                    out.append((s, i, key(r["row"]), r["value"], r["threshold"]))
    return out


def summary(run, seeds):
    t = [d["manifest"]["train"] for d in seeds.values()]
    q4 = [os.path.getsize(os.path.join(d["dir"], "model_q4.bin")) for d in seeds.values()
          if os.path.exists(os.path.join(d["dir"], "model_q4.bin"))]
    nll = [x["goal_nll"] for x in t]
    return {"run": run, "seeds": len(seeds), "params_m": t[0]["params_m"] if t else None,
            "q4_mb": q4[0] / 1e6 if q4 else None, "goal_nll_mean": statistics.fmean(nll) if nll else None,
            "goal_nll_min": min(nll) if nll else None, "goal_nll_max": max(nll) if nll else None}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--reference", default="fish-14m-all")
    ap.add_argument("--markdown", default=None)
    ap.add_argument("--json", default=None)
    args = ap.parse_args()
    ref = load_run(args.reference)
    if not ref:
        sys.exit(f"reference {args.reference}: no finished seeds under {OUT}")
    rv = row_values(ref)
    lines = [f"# Size sweep verdict (reference {args.reference}, {len(ref)} seeds)", "",
             "Rules fixed before the run: issue #1, comment of 2026-11-09 21:35. A row's value per seed is the mean "
             "of its probe panels.", "",
             "Reference range per row (lowest - highest over its seeds):", ""]
    for k, e in rv.items():
        vals = [v for sk, v in e.items() if isinstance(sk, int)]
        lines.append(f"- {e['name']} ({e['bar']}): {min(vals):.3f} - {max(vals):.3f}")
    ref_nll = [d["manifest"]["train"]["goal_nll"] for d in ref.values()]
    lines += [f"- goal NLL: {min(ref_nll):.4f} - {max(ref_nll):.4f}", "",
              "| run | seeds | params | q4 MB | goal NLL mean (min-max) | tier A | tier A misses | tier B misses (of seeds x panels) |",
              "|---|---|---|---|---|---|---|---|"]
    results = []
    for run in [args.reference] + [r for r in args.runs if r != args.reference]:
        seeds = load_run(run)
        if not seeds:
            lines.append(f"| {run} | 0 | - | - | - | not run | - | - |")
            continue
        s = summary(run, seeds)
        ok, fails = tier_a(seeds, ref) if run != args.reference else (True, [])
        b = tier_b(seeds)
        miss = ", ".join(sorted({f"{k}" for _, k, _, _ in fails})) or "-"
        bmiss = ", ".join(f"{k} {n}" for k, n in sorted(
            {k: sum(1 for x in b if x[2] == k) for _, _, k, _, _ in b}.items())) or "-"
        lines.append(f"| {run} | {s['seeds']} | {s['params_m']:.2f}M | {s['q4_mb']:.2f} | {s['goal_nll_mean']:.4f} "
                     f"({s['goal_nll_min']:.4f}-{s['goal_nll_max']:.4f}) | "
                     f"{'reference' if run == args.reference else 'PASS' if ok else 'fail'} | {miss} | {bmiss} |")
        results.append(dict(s, tier_a=ok if run != args.reference else None, tier_a_fails=fails, tier_b_fails=b))
    passing = [r for r in results if r["tier_a"]]
    best = min(passing, key=lambda r: r["params_m"]) if passing else None
    lines += ["", f"Smallest run passing tier A: **{best['run']}** ({best['params_m']:.2f}M params, "
                  f"{best['q4_mb']:.2f} MB q4)" if best else "", "" if best else "No run besides the reference passes tier A."]
    ref_b = tier_b(ref)
    if ref_b:
        lines += ["", "The reference itself misses these upstream bars (so no size is declared a winner on tier B): "
                  + ", ".join(sorted({k for _, _, k, _, _ in ref_b}))]
    text = "\n".join(lines) + "\n"
    print(text)
    if args.markdown:
        open(args.markdown, "w").write(text)
    if args.json:
        json.dump({"reference": args.reference, "results": results}, open(args.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
