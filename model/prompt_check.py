#!/usr/bin/env python3
"""Check a teacher prompt BEFORE the overnight run. Stdlib only.

The v3 overnight taught us the expensive way that one sentence in the teacher
prompt reshapes every label (P(follow | social>=8) fell 0.50 -> 0.18). This
asks the teacher ~300 questions on a fixed diagnostic panel and prints the
conditional rates the student will inherit - ~7 minutes with 3 workers, not
8 hours. Use it to compare prompts, or teachers (--model qwen3.5:27b ...).

  python3 prompt_check.py --schema 3                       # current v3 prompt
  python3 prompt_check.py --schema 3 --prompt-file cand.txt # a candidate prompt
  python3 prompt_check.py --schema 3 --model qwen3.5:27b   # another teacher
  python3 prompt_check.py --schema 4 --api openai --host http://localhost:8080/v1 --model <name> \
      --temperature 1.0 --label-seed 7 --out out/check.json  # an OpenAI-compatible server, seeded, saved

--label-seed gives every question a seed (from the base seed, its place in the panel and the state),
so the same panel, teacher and settings give the same answers in any worker order. --out writes every
question and answer with the run's settings (gen_traces.teacher_meta) to a JSON file.

Panel (per schema line, identity randomized unless the case pins it):
  social9   content fish, social 9 (expect follow_friend high)     x40
  social1   content fish, social 1 (expect follow_friend ~0)        x40
  bold9     content + energetic, bold 9 (expect dart_play present)  x40
  bold1     same, bold 1 (expect dart_play ~0)                      x40
  content   content, mid identity (watch for a single attractor)    x40
  shadowcalm shadow near, stress 0-3 (expect flee high)             x40
  lonely    friend none, content (must not flee / seek food)        x30
  starving  hunger 9, food near (expect seek_food ~1.0)             x30
  trust     content, trust 9 vs trust 0 (v3 only; expect a shade, not a flip) x40
  v4 (--schema 4; the shadow cases are skipped, bored cases added):
  bored9bub  content, bored 9, last visit_bubbles (expect a change, explore up) x40
  bored9fol  social 8, friend near, bored 9, last follow_friend (expect a change) x40
  bored0bub  content, bored 0, last visit_bubbles (expect last mostly KEPT)     x40
  nightbored night, bored 9, last rest (expect rest - boredom never wakes the tank) x30
"""
import argparse
import concurrent.futures as cf
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_traces as gt  # noqa: E402


def state(rng, schema, **pin):
    f = dict(zone=rng.randint(1, 6), hunger=rng.randint(0, 3), energy=rng.randint(5, 9), stress=rng.randint(0, 2),
             curiosity=rng.randint(3, 8), bold=rng.randint(2, 7), social=rng.randint(2, 6),
             stage=rng.choice(["juv", "adult", "adult", "elder"]), trust=rng.randint(2, 7),
             bored=rng.randint(0, 2), food="none", shadow="none", friend=f"{rng.choice(['near','mid'])} {rng.randint(1,12)}",
             bubble=f"{rng.choice(['near','mid','far'])} {rng.randint(1,12)}",
             reef=f"{rng.choice(['mid','far'])} {rng.randint(1,12)}", wall="clear",
             last=rng.choice(["explore", "inspect_reef", "visit_bubbles", "rest"]), time="day")
    f.update(pin)
    ident = f"hunger {f['hunger']} energy {f['energy']} stress {f['stress']} curiosity {f['curiosity']} bold {f['bold']} social {f['social']} stage {f['stage']}"
    tail = (f"food {f['food']} shadow {f['shadow']} friend {f['friend']} bubble {f['bubble']} reef {f['reef']} "
            f"wall {f['wall']} last {f['last']} time {f['time']}")
    if schema >= 4:
        return (f"zone {f['zone']} {ident} trust {f['trust']} bored {f['bored']} food {f['food']} friend {f['friend']} "
                f"bubble {f['bubble']} reef {f['reef']} wall {f['wall']} last {f['last']} time {f['time']}")
    if schema >= 3:
        return f"zone {f['zone']} {ident} trust {f['trust']} {tail}"
    name = rng.choice(["mira", "bolt", "kelp", "nori"])
    fr = f['friend'] if f['friend'] == "none" else f"{rng.choice(['mira','bolt','kelp','nori'])} {f['friend']}"
    return f"fish {name} zone {f['zone']} {ident} {tail.replace('friend ' + f['friend'], 'friend ' + fr, 1)}"


def panel(rng, schema, n, extra=False):
    """the diagnostic panel: [(case, state line)]. extra (schema 4 only) appends cases after the
    upstream ones, so the upstream states and their order are unchanged:
      fedfood  hunger 1-3 and food near, drawn per state (the panel's other states never show food
               unless starving; a teacher that eats at low hunger skews the training data, issue #1)"""
    P = []
    def add(case, k, **pin):
        for _ in range(int(n * k / 40)):
            P.append((case, state(rng, schema, **pin)))
    add("social9", 40, social=9)
    add("social1", 40, social=1)
    add("bold9", 40, bold=9, energy=9, hunger=rng.randint(0, 2))
    add("bold1", 40, bold=1, energy=9, hunger=rng.randint(0, 2))
    add("content", 40)
    if schema < 4:
        add("shadowcalm", 40, shadow=f"near {rng.randint(1,12)}", stress=rng.randint(0, 3))
    add("lonely", 30, friend="none")
    add("starving", 30, hunger=9, food=f"near {rng.randint(1,12)}")
    if schema >= 3:
        add("trust9", 20, trust=9)
        add("trust0", 20, trust=0)
    if schema >= 4:
        add("bored9bub", 40, bored=9, last="visit_bubbles", bubble=f"near {rng.randint(1,12)}")
        add("bored9fol", 40, bored=9, last="follow_friend", social=8, friend=f"near {rng.randint(1,12)}")
        add("bored0bub", 40, bored=0, last="visit_bubbles", bubble=f"near {rng.randint(1,12)}")
        add("nightbored", 30, bored=9, last="rest", time="night", energy=rng.randint(3, 6), reef=f"near {rng.randint(1,12)}")
        if extra:
            for _ in range(int(n * 30 / 40)):
                P.append(("fedfood", state(rng, schema, hunger=rng.randint(1, 3), food=f"near {rng.randint(1, 12)}")))
    return P


V4_CASE_ORDER = ("social9", "social1", "bold9", "bold1", "content", "lonely", "starving", "trust9", "trust0",
                 "bored9bub", "bored9fol", "bored0bub", "nightbored", "fedfood")


def mean_dist(by, case):
    """a case's goals as shares of all its weight: a teacher's answer mix, a student's mean distribution"""
    rows = by.get(case, [])
    tot = sum(w for _, d in rows for w in d.values())
    out = {}
    for _, d in rows:
        for g, w in d.items():
            out[g] = out.get(g, 0.0) + w / tot
    return out


def v4_table(by, flee=True):
    """THE v4 (FISH) ROWS, for the teacher (this script) and a trained student (probe_fish.py) alike.
    by: case -> [(state, {goal: weight})]: a teacher's answer carries weight 1 on its goal, a student's
    state its goal distribution; a row's value is the share of the weight on the row's goal (the
    teacher's rate, the student's expected rate). The bars are upstream's (prompt_check's v4 checks).
    Returns [(row, value, n, want, ok)], ok None for a report row; rows whose case did not run are left out.
    F12: the weight on flee_shadow, which no v4 label uses (the student's leak onto that token)."""
    def rate(case, goal):
        rows = by.get(case, [])
        tot = sum(w for _, d in rows for w in d.values())
        return (sum(d.get(goal, 0.0) for _, d in rows) / tot if tot else float("nan")), len(rows)
    rows = [
        ("F1  P(follow | social 9)", *rate("social9", "follow_friend"), ">= 0.40", lambda v: v >= 0.40),
        ("F2  P(follow | social 1)", *rate("social1", "follow_friend"), "<= 0.05", lambda v: v <= 0.05),
        ("F3  P(dart | bold 9, energetic)", *rate("bold9", "dart_play"), ">= 0.10", lambda v: v >= 0.10),
        ("F4  P(dart | bold 1, energetic)", *rate("bold1", "dart_play"), "<= 0.03", lambda v: v <= 0.03),
        ("F5  P(seek_food | starving)", *rate("starving", "seek_food"), ">= 0.95", lambda v: v >= 0.95),
        ("F6  P(seek_food | lonely, not hungry)", *rate("lonely", "seek_food"), "<= 0.05", lambda v: v <= 0.05),
        ("F7  P(bubbles again | bored 9, last bubbles)", *rate("bored9bub", "visit_bubbles"), "<= 0.15", lambda v: v <= 0.15),
        ("F8  P(explore | bored 9, last bubbles)", *rate("bored9bub", "explore"), ">= 0.25", lambda v: v >= 0.25),
        ("F9  P(follow again | bored 9, last follow)", *rate("bored9fol", "follow_friend"), "<= 0.15", lambda v: v <= 0.15),
        ("F10 P(bubbles kept | bored 0, last bubbles)", *rate("bored0bub", "visit_bubbles"), ">= 0.40", lambda v: v >= 0.40),
        ("F11 P(rest | night, bored 9, last rest)", *rate("nightbored", "rest"), ">= 0.70", lambda v: v >= 0.70),
    ]
    if flee:
        tot = sum(w for rs in by.values() for _, d in rs for w in d.values())
        fl = sum(d.get("flee_shadow", 0.0) for rs in by.values() for _, d in rs)
        rows.append(("F12 P(flee | any v4 case)", fl / tot if tot else float("nan"), sum(len(rs) for rs in by.values()),
                     "== 0", lambda v: v <= 0.001))
    content = mean_dist(by, "content")
    if content:
        g, mx = max(content.items(), key=lambda kv: kv[1])
        rows.append((f"F13 max single goal | content ({g})", mx, len(by["content"]), "< 0.45", lambda v: v < 0.45))
    rows.append(("F14 P(seek_food | hunger 1-3, food near) (report)", *rate("fedfood", "seek_food"), "-", None))
    return [(name, v, n, want, ok(v) if ok else None) for name, v, n, want, ok in rows if n]


def report_v4(rows):
    """print the v4 table for a teacher's answers: rows [{case, state, answer}] (an --out file's rows)"""
    by = {}
    for r in rows:
        if r.get("answer"):
            by.setdefault(r["case"], []).append((r["state"], {r["answer"].split()[0]: 1.0}))
    table = v4_table(by)
    for name, v, n, want, ok in table:
        print(f"  {'rep' if ok is None else 'OK ' if ok else 'BAD'}  {name:52s} = {v:.2f}  (n={n}, want {want})")
    print("\n  per case:")
    for case in V4_CASE_ORDER:
        if case in by:
            d = mean_dist(by, case)
            print(f"    {case:10s} " + ", ".join(f"{g} {p:.2f}" for g, p in sorted(d.items(), key=lambda kv: -kv[1])[:3]))
    return table


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--schema", type=int, choices=(2, 3, 4), default=3)
    ap.add_argument("--api", choices=("ollama", "openai"), default="ollama",
                    help=f"teacher API (as gen_traces; openai key from ${gt.TEACHER_KEY_ENV})")
    ap.add_argument("--host", default=None, help=f"teacher base URL (ollama default {gt.API_DEFAULT_HOST['ollama']}; "
                    "openai: required)")
    ap.add_argument("--model", default="gemma4:26b")
    ap.add_argument("--temperature", type=float, default=gt.TEACHER_TEMPERATURE)
    ap.add_argument("--label-seed", type=int, default=None, help="base seed for the teacher's sampling (default: none)")
    ap.add_argument("--max-tokens", type=int, default=gt.TEACHER_MAX_TOKENS, help="the teacher's answer budget (as gen_traces)")
    ap.add_argument("--reasoning-effort", choices=("low", "medium", "high"), default=None,
                    help="openai: let a reasoning teacher think at this effort (default: thinking off)")
    ap.add_argument("--out", default=None, help="write every question, answer and the run's settings to this JSON file")
    ap.add_argument("--prompt-file", default=None, help="candidate system prompt (default: gen_traces' prompt for the schema)")
    ap.add_argument("--n", type=int, default=40, help="calls per major case (default 40 -> ~320 calls)")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--extra-cases", action="store_true",
                    help="schema 4: append the extra cases (fedfood) after upstream's, which stay unchanged")
    ap.add_argument("--rescore", default=None, metavar="FILE",
                    help="schema 4: print the v4 table for a saved --out file and stop (no teacher calls)")
    args = ap.parse_args()
    gt.SCHEMA = args.schema
    gt.TEACHER_MAX_TOKENS, gt.TEACHER_REASONING = args.max_tokens, args.reasoning_effort
    if args.rescore:
        d = json.load(open(args.rescore))
        print(f"{args.rescore}: {d.get('model')} T={d.get('temperature')} label_seed={d.get('label_seed')}, "
              f"{len(d['rows'])} questions, {sum(1 for r in d['rows'] if not r.get('answer'))} unanswered")
        report_v4(d["rows"])
        return
    if args.prompt_file:
        txt = open(args.prompt_file).read().strip()
        gt.SYSTEM_PROMPT = txt
        gt.SYSTEM_PROMPT_V3 = txt
        gt.SYSTEM_PROMPT_V4 = txt
    host = args.host or gt.API_DEFAULT_HOST[args.api]
    if not host:
        ap.error("--api openai needs --host (the server's base URL, e.g. http://localhost:8080/v1)")
    rng = random.Random(args.seed)
    P = panel(rng, args.schema, args.n, extra=args.extra_cases and args.schema >= 4)
    print(f"{len(P)} calls to {args.model} @ {host} ({args.api}, {args.workers} workers, temperature "
          f"{args.temperature}, label seed {args.label_seed}) ...", flush=True)

    def ask(item):
        i, (case, st) = item
        try:
            g = gt.ask_teacher(args.api, host, args.model, st, 30, args.temperature,
                               gt.label_seed(args.label_seed, i, st))
        except Exception as e:  # noqa: BLE001
            g = None
        return case, st, g

    results = {}
    rows = []
    fails = 0
    with cf.ThreadPoolExecutor(args.workers) as ex:
        for case, st, g in ex.map(ask, enumerate(P)):
            rows.append({"case": case, "state": st, "answer": g})
            goal = g.split()[0] if g else None
            if goal is None:
                fails += 1
                continue
            results.setdefault(case, {}).setdefault(goal, 0)
            results[case][goal] += 1
    if args.out:
        meta = dict(gt.teacher_meta(args.api, host, args.model, args.temperature, args.label_seed),
                    panel_seed=args.seed, n=args.n, workers=args.workers, prompt_file=args.prompt_file)
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w") as fh:
            json.dump(dict(meta, rows=rows), fh, indent=1)
        print(f"-> {args.out}")

    def rate(case, goal):
        d = results.get(case, {}); n = sum(d.values())
        return (d.get(goal, 0) / n if n else float("nan")), n

    def top(case):
        d = results.get(case, {}); n = sum(d.values()) or 1
        return ", ".join(f"{g} {c/n:.2f}" for g, c in sorted(d.items(), key=lambda kv: -kv[1])[:3])

    print(f"\nfailures: {fails}")
    if args.schema >= 4:     # the v4 table: one table for the teacher and for probe_fish.py's students
        report_v4(rows)
        return
    checks = [
        ("P(follow | social 9)", *rate("social9", "follow_friend"), ">= 0.40", lambda v: v >= 0.40),
        ("P(follow | social 1)", *rate("social1", "follow_friend"), "<= 0.05", lambda v: v <= 0.05),
        ("P(dart | bold 9, energetic)", *rate("bold9", "dart_play"), ">= 0.10", lambda v: v >= 0.10),
        ("P(dart | bold 1, energetic)", *rate("bold1", "dart_play"), "<= 0.03", lambda v: v <= 0.03),
        ("P(seek_food | starving)", *rate("starving", "seek_food"), ">= 0.95", lambda v: v >= 0.95),
        ("P(seek_food | lonely, not hungry)", *rate("lonely", "seek_food"), "<= 0.05", lambda v: v <= 0.05),
    ]
    if args.schema < 4:
        checks += [
            ("P(flee | shadow near, calm)", *rate("shadowcalm", "flee_shadow"), ">= 0.80", lambda v: v >= 0.80),
            ("P(flee | lonely, no shadow)", *rate("lonely", "flee_shadow"), "== 0", lambda v: v <= 0.02),
        ]
    else:
        checks += [
            ("P(bubbles again | bored 9, last bubbles)", *rate("bored9bub", "visit_bubbles"), "<= 0.15", lambda v: v <= 0.15),
            ("P(explore | bored 9, last bubbles)", *rate("bored9bub", "explore"), ">= 0.25", lambda v: v >= 0.25),
            ("P(follow again | bored 9, last follow)", *rate("bored9fol", "follow_friend"), "<= 0.15", lambda v: v <= 0.15),
            ("P(bubbles kept | bored 0, last bubbles)", *rate("bored0bub", "visit_bubbles"), ">= 0.40", lambda v: v >= 0.40),
            ("P(rest | night, bored 9, last rest)", *rate("nightbored", "rest"), ">= 0.70", lambda v: v >= 0.70),
            ("P(flee | any v4 case)", (sum(d.get("flee_shadow", 0) for d in results.values()) / max(1, sum(sum(d.values()) for d in results.values()))), sum(sum(d.values()) for d in results.values()), "== 0", lambda v: v <= 0.001),
        ]
    for name, v, n, want, ok in checks:
        print(f"  {'OK ' if ok(v) else 'BAD'}  {name:36s} = {v:.2f}  (n={n}, want {want})")
    # attractor check: no single goal should own the content fish
    d = results.get("content", {}); n = sum(d.values()) or 1
    mx = max(d.values()) / n if d else 0
    print(f"  {'OK ' if mx < 0.45 else 'BAD'}  {'max single goal | content':36s} = {mx:.2f}  (want < 0.45)   [{top('content')}]")
    if args.schema >= 3:
        print(f"       trust 9: [{top('trust9')}]\n       trust 0: [{top('trust0')}]")
    print("\n  per case:")
    for case in ("social9", "social1", "bold9", "bold1", "content", "shadowcalm", "lonely", "starving", "trust9", "trust0",
                 "bored9bub", "bored9fol", "bored0bub", "nightbored"):
        if case in results:
            print(f"    {case:10s} {top(case)}")


if __name__ == "__main__":
    main()
