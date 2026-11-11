# Candidate 3: fish-d256-n6-decision on fish-v4-mix-cov-bigplay-relabel, seed 1 (issue #1)

The same 4.8M shape as candidates 1 and 2 (2,579,888 B at 4 bits). **A test candidate, not a replacement:**
`model/out/model_q4.bin` is still the shipped model.

| File | What |
|---|---|
| `model_q4.bin`, `model_trailer.bin` (tag `relabel-d256n6`), `SHA256SUMS` | the model and its trailer |
| `run/` | harness record: `manifest.json` (git e888a5b, clean; dataset f16bd193; marvin's Radeon 8060S; kept iteration 4,000), `train.log`, probes on panels 11, 23, 37, the run's `report.md` (3 seeds) |
| `acceptance/` | upstream's acceptance checks on this file |

## What changed from candidate 2 (one thing: the data)

Dataset `fish-v4-mix-cov-bigplay-relabel` (28,948 pairs, sha256 `f16bd193…`, the same count as candidate 2's) is
candidate 2's with one context relabelled. The 31B's pairs at hunger 1-3 with food in view (4,021 of its 13,500)
were answered again by the 26B. Tool: `relabel.py --hunger 1-3 --food-in-view`, label seed 4701, both cards, 0
failures; 1,757 changed goal. seek_food in those pairs went from about 58% to 17%. Why: the 31B eats with fed fish (77%
at hunger 1-3 with food near, against the 26B's 34%), and candidate 2 copied it (F14 0.65, stock 0.15). Cutting the
31B's share instead also cuts following (26B-only students F1 0.05).

## Checks

**Panel rows** (student probe n=400): every row passes on panels 11, 23 and 37.
- F14 (fed, food near: seek_food): 0.285 / 0.257 / 0.303 (candidate 2 0.65, stock 0.15).
- F3 dart: 0.37 / 0.25 / 0.24. F4 timid: <= 0.007.

**Eating curve**, food near, hunger 0 -> 8 (`eat_by_hunger.py`):

| | h0 | h1 | h2 | h3 | h4 | h5 | h6 | h7 | h8 |
|---|---|---|---|---|---|---|---|---|---|
| stock | 0.01 | 0.23 | 0.05 | 0.14 | 0.33 | 0.50 | 0.72 | 0.98 | 0.99 |
| candidate 2 | 0.12 | 0.77 | 0.46 | 0.62 | 0.77 | 0.84 | 0.90 | 0.97 | 0.98 |
| this model | 0.07 | 0.54 | 0.10 | 0.20 | 0.62 | 0.74 | 0.85 | 0.95 | 0.98 |

- The rule's guard (hunger 4-5 within 0.05 of candidate 2) was missed. Daniel accepted that: these fish still eat
  about twice what the shipped model eats there.
- Dart by hunger: 0.34 / 0.23 / 0.24 at hunger 0 / 1 / 2, timid <= 0.006.
- Replayed pendant states (`pendant_replay.py`, the 470 states of the three earlier pendant logs):
  - fed fish with food in view eat 0.137 (candidate 2 0.261, stock 0.056)
  - timid dart 0.020 (candidate 2 0.009, stock 0.021)
  - bold dart 0.190

**Upstream's acceptance** (`docs/retrain-v4.md`), against stock and candidate 2:

| check (bar) | stock 14M | candidate 2 | **this model** |
|---|---|---|---|
| agreement with the 26B (>= 72%) / 31B, n=300 | **68%** / 58% | 74% / 77% | 75% / 74% |
| bubbles kept at bored 0 / 1 (>= 0.4) | **0.21 / 0.20** | 0.84 / **0.36** | 0.59 / 0.51 |
| ... dropped at bored 8-9, explore rises | 0.00, 1.00 | 0.00, 1.00 | 0.00, 0.99-1.00 |
| social 8, bored 9 leaves the friend | follow 0.32 | follow 0.00 | follow 0.01 |
| night + bored 9 rests / starving + bored 9 eats (>= 0.85) | 0.99 / 0.97 | 0.99 / 0.95 | 1.00 / 0.96 |
| follow cliff social 0 -> 9 (v3m 0.01 -> 0.52) | 0.05 -> 0.54 | 0.01 -> 0.74 | 0.00 -> 0.55 |
| dart cliff bold 0 -> 9 (v3m 0.02 -> 0.40) | 0.03 -> **0.19** | 0.01 -> 0.46 | 0.00 -> **0.15** |
| census 1 min x3: landmark (< 59%) | 58 / 54 / **64** | 41 / 32 / 39 | 30 / 43 / 31 |
| census 1 min x3: longest stretch (< 59 s) | **59** / 54 / **59** | **60** / 37 / 37 | 36 / **60** / 36 |
| census 1 min x3: zones (> 1.5), bored (< 3.3) | 2.8-3.5, 1.7-1.9 | 2.8-4.0, 1.1-1.4 | 2.8-3.2, 1.3-1.6 |
| census 10 min x2: landmark / longest / bored | **59%**, **256 s**, **4.5** | **59%**, **61 s**, **3.3** | 58%, **87 s**, **3.5** (both runs identical) |

**Bold** = misses the bar.
- Counted the same way, this model misses 3 bars, candidate 2 4, the shipped model 6.
- The dart cliff is an average over 6 hand-written states and swings by seed: seeds 1 / 2 / 3 score 0.15 / 0.35 / 0.28
  (`acceptance/probe_dist-relabel-s{2,3}.txt`, from the fp32 checkpoints). Seed 1 is the harness's pick and is kept as picked.

## On the pendant (same 1.75C board, 2026-11-10 16:30; `pendant/pendant-c3.log`)

| | stock 14M | candidate 1 | candidate 2 | **this model** |
|---|---|---|---|---|
| log | 16.1 min, 3 fish | 12.5 min, 2-3 fish | 11.5 min, 3 fish | 9.3 min, 3 fish |
| time per decision, median (range) | 3,644 ms | 1,474 ms | 1,466 ms | **1,472 ms** (1,268-1,876) |
| tokens/s | 11.8 | 29.8 | 29.8 | 29.3 |
| internal heap / PSRAM free (flat) | 35 / 1,227 KB | 62 / 1,669 KB | 62 / 1,591 KB | 62 / 1,675 KB |
| asks / decisions | 259 / 209 | 119 / 119 | 156 / 150 | 153 / 150 |
| goal changes per fish-minute | 2.16 | 2.10 | 2.17 | 2.07 |
| dart decisions (the fish's bold) | 4 / 210 (1, 8, 8, 8) | 6 / 111 (all 8) | 9 / 149 (1, 3, 3, 3, 8 x5) | **12 / 147 (all 8)** |
| fed (hunger 0-2), food in view: seek_food | 2 / 38 | 16 / 56 | 18 / 70 | **9 / 61** |

Replaying this session's 147 states (`pendant_replay.py`):

| | fed, food in view: seek_food | timid dart |
|---|---|---|
| stock | 0.018 | 0.024 |
| candidate 2 | 0.249 | 0.019 |
| this model | 0.156 | 0.015 |

## Repeat

1. `python3 harness.py run fish-d256-n6-decision-relabel`. It needs the label files under `out/data/`, which are not
   in git; regenerate them with `run_teacher_jobs.sh` as for candidate 2.
2. The relabel step:
   - `python3 relabel.py --split <the 31B files> --kept out/data/fish31b-relabel/kept-31b-h1-3food.jsonl --hunger 1-3 --food-in-view`
   - then twice, for `--shard 0/2` and `--shard 1/2`: `python3 relabel.py --relabel <same files, same order>
     --out out/data/fish31b-relabel/relabel26b-h1-3food-s<k>of2.jsonl --hunger 1-3 --food-in-view --api openai
     --host URL --model <26B> --label-seed 4701 --shard <k>/2`
3. Trailer: `python3 ../tools/model_trailer.py --model model_q4.bin --out model_trailer.bin --tag relabel-d256n6`.
