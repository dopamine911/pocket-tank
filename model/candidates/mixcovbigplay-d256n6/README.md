# Candidate 2: fish-d256-n6-decision on fish-v4-mix-cov-bigplay, seed 1 (issue #1)

The same 4.8M shape as `../mixcov-d256n6/` (dim 256, 6 layers, 8 heads, 2,579,888 B at 4 bits), trained on the
same data plus 2,250 states labelled by a third teacher to fix dart. **A test candidate, not a replacement:**
`model/out/model_q4.bin` is still the shipped model.

| File | What |
|---|---|
| `model_q4.bin`, `model_trailer.bin` (tag `bigplay-d256n6`), `SHA256SUMS` | the model and its trailer |
| `run/` | harness record: `manifest.json` (git cf0175e, clean; dataset a52e8648; marvin's Radeon 8060S), `train.log`, probes on panels 11, 23, 37, the run's `report.md` (3 seeds) |
| `acceptance/` | upstream's acceptance checks on this file (as in `../mixcov-d256n6/acceptance/`) |

## What changed from candidate 1 (one thing: the data)

Dataset `fish-v4-mix-cov-bigplay` (28,948 pairs, sha256 `a52e8648…`) = `fish-v4-mix-cov` (26B + 31B, 50/50, with
no-food coverage) + one shard of 2,250 samples from `gen_traces.py --play 0.6` (sim 611, label seed 3611): about 6 in
10 daytime samples turned into a rested, fed fish with no food in view, at every boldness, labelled by **big**
(Qwen3.8-Flash-Next UD-IQ4_XS on llama.cpp, marvin). On those states big darts with 23% of bold fish and no timid
fish; the 26B and 31B dart with 1.4% and 7.5% (and our first try with their labels made dart worse).

## Checks

Panel rows (student probe n=400): every row passes on panels 11, 23 and 37 (F3 dart 0.37 / 0.42 / 0.25, F4 timid
dart 0.011 / 0.010 / 0.003, F10 0.57 / 0.61, F13 0.32 / 0.33 / 0.32). F14 (fed, food near: seek_food, report only)
0.65 / 0.63 (stock 0.15). Dart by hunger (`dart_by_hunger.py`): 0.36 / 0.24 / 0.41 at hunger 0 / 1 / 2, timid
<= 0.010. On realistic sim states (`dart_on_sim.py`) 0.115 (stock 0.059, the teachers' own labels 0.044).

Upstream's acceptance (`docs/retrain-v4.md`), against stock and candidate 1:

| check (bar) | stock 14M | candidate 1 | **this model** |
|---|---|---|---|
| agreement with the 26B (>= 72%), n=300 | 68% | 71% | **74%** |
| agreement with the 31B, n=300 | 58% | 73% | **77%** |
| bubbles kept at bored 0 / 1 (>= 0.4) | 0.21 / 0.20 | 0.89 / 0.85 | 0.84 / **0.36** |
| ... dropped at bored 8-9, explore rises | 0.00, 1.00 | 0.00, 1.00 | 0.00, 1.00 |
| social 8, bored 9 leaves the friend | follow 0.32 | follow 0.01 | follow 0.00 |
| night + bored 9 rests / starving + bored 9 eats (>= 0.85) | 0.99 / 0.97 | 1.00 / 0.95 | 0.99 / 0.95 |
| follow cliff social 0 -> 9 (v3m 0.01 -> 0.52) | 0.05 -> 0.54 | 0.01 -> 0.82 | 0.01 -> 0.74 |
| dart cliff bold 0 -> 9 (v3m 0.02 -> 0.40) | 0.03 -> **0.19** | 0.00 -> **0.01** | 0.01 -> 0.46 |
| census 1 min x3: landmark (< 59%) | 58 / 54 / **64** | **70 / 70** / 45 | 41 / 32 / 39 |
| census 1 min x3: longest stretch (< 59 s) | **59** / 54 / **59** | **60 / 60** / 30 | **60** / 37 / 37 |
| census 1 min x3: zones (> 1.5), bored (< 3.3) | 2.8-3.5, 1.7-1.9 | 1.8-2.5, 1.7-2.5 | 2.8-4.0, 1.1-1.4 |
| census 10 min x2: landmark / longest / bored | **59** / 54%, **256 / 261 s**, **4.5 / 4.7** | 54%, **82 s**, **4.2** | **59%**, **61 s**, **3.3** (both runs identical) |

**Bold** = misses the bar. Still open: bubbles kept at bored 1 (0.36), eating when fed (F14), and the 10-minute
census sits right at upstream's 1-minute bars.

## On the pendant (same 1.75C board, 2026-11-10 15:05; `pendant/pendant-c2.log`)

| | stock 14M | candidate 1 | **this model** |
|---|---|---|---|
| log | 16.1 min, 3 fish | 12.5 min, 2-3 fish | 11.5 min, 3 fish |
| time per decision, median (range) | 3,644 ms | 1,474 ms (1,220-1,604) | **1,466 ms** (1,296-1,541) |
| tokens/s | 11.8 | 29.8 | 29.8 |
| internal heap / PSRAM free (flat) | 35 / 1,227 KB | 62 / 1,669 KB | 62 / 1,591 KB |
| asks / decisions | 259 / 209 | 119 / 119 | 156 / 150 |
| goal changes per fish-minute (10 s status lines) | 2.16 | 2.10 | 2.17 |
| dart decisions (bold of the fish) | 4 of 210 (1, 8, 8, 8) | 6 of 111 (all 8) | 9 of 149 (1, 3, 3, 3, 8 x5) |
| fed, food in view: seek_food | 2 of 38 | 16 of 56 | 18 of 70 |

The 4 timid darts were energetic (8-9) juvenile fish; the model gives dart 0.07-0.29 there (the `p=` the device
logged, reproduced by `pendant_replay.py` on the q4 file). Replaying each session's states through all three models,
mean P(dart) for timid fish: candidate-1 session stock 0.004 / c1 0.004 / **c2 0.001**; this session stock 0.050 /
c1 0.006 / **c2 0.024**; stock session stock 0.006 / c1 0.003 / **c2 0.002**: at or below the shipped model's in every
session (this session's timid fish drew dart from stock 0.050 and from this model 0.024; candidate 1 barely, 0.006). PSRAM 78 KB lower than candidate 1 with the same
model shape: not explained (different tank state, 3 fish throughout).

## Repeat

`python3 harness.py run fish-d256-n6-decision-mixcovbigplay` (needs the label files under `out/data/`, not in git;
`run_teacher_jobs.sh` regenerates them from the same seeds: `HOST=... MODEL=marvin/big PLAY=0.6
run_teacher_jobs.sh "gen 0.7 3611 2250 611"`). Trailer: `python3 ../tools/model_trailer.py --model model_q4.bin
--out model_trailer.bin --tag bigplay-d256n6`. Acceptance: as in `../mixcov-d256n6/acceptance/README.md`.
