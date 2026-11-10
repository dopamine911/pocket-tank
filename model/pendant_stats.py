#!/usr/bin/env python3
"""pendant_stats.py - summarise a pendant serial log (pocket-tank issue #1): decision time, memory, goals, errors.
   python3 pendant_stats.py candidates/mixcov-d256n6/pendant/pendant-4.8m.log candidates/mixcov-d256n6/pendant/pendant-stock.log"""
import re, statistics as st, sys
from collections import Counter

def stats(path):
    ms, status, adv, prof, i2c = [], [], [], [], 0
    for line in open(path, errors="replace"):
        m = re.match(r"[IEW] \((\d+)\)", line)
        if m: ms.append(int(m.group(1)))
        if "I2C transaction failed" in line: i2c += 1
        if "pocket-tank: t=" in line:
            s = re.search(r"t=(\d+)s (\d+) fish .*asks (\d+) decisions (\d+) last (\d+) ms ([\d.]+) tok/s \| starve-ignored (\d+) \| heap int (\d+) KB psram (\d+) KB", line)
            if s: status.append(tuple(float(x) for x in s.groups()))
        if "advisor: zone" in line:
            a = re.search(r"hunger (\d+) .*?food (\w+).* -> (\w+)", line)
            if a: adv.append((int(a.group(1)), a.group(2), a.group(3)))
        if "advisor: prof ms" in line:
            prof.append(sum(int(x) for x in re.findall(r"\b[a-z/]+ (\d+)", line.split("prof ms:")[1])))
    # one decision time per new decision: take status lines where the decision count moved
    last, seen = [], None
    for s in status:
        if s[3] != seen: last.append((s[4], s[5])); seen = s[3]
    goals = Counter(g for _, _, g in adv)
    fed_food = [g for h, f, g in adv if h <= 2 and f != "none"]
    q = lambda xs: (min(xs), st.median(xs), max(xs))
    return dict(
        minutes=round((ms[-1] - ms[0]) / 60000, 1), tank_t=(int(status[0][0]), int(status[-1][0])),
        fish=(int(min(s[1] for s in status)), int(max(s[1] for s in status))),
        asks=int(status[-1][2]), decisions=int(status[-1][3]), starve_ignored=int(max(s[6] for s in status)),
        decision_ms=q([x for x, _ in last]), tok_s=q([y for _, y in last]), prof_ms=q(prof),
        heap_int_kb=q([s[7] for s in status]), psram_kb=q([s[8] for s in status]),
        advisor_lines=len(adv), goals=dict(goals.most_common()),
        fed_food_seek=f"{fed_food.count('seek_food')} of {len(fed_food)}", i2c_failed_lines=i2c)

for p in sys.argv[1:]:
    print(f"== {p}")
    for k, v in stats(p).items(): print(f"  {k}: {v}")
