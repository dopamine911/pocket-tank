# A smaller fish model: 4.8M parameters, 2.6 MB (2026-11)

This PR adds one file set, `model/candidates/relabel-d256n6/` (the 4-bit model, its trailer, checksums), and this
note. **It does not change the shipped model.** `model/out/model_q4.bin` and everything that reads it are untouched.

The tools, the full training records and the raw check outputs live on the branch that produced the model:
[`dopamine911/pocket-tank@2a99329`](https://github.com/dopamine911/pocket-tank/tree/2a99329/model) (`feat/training-harness-31b`).
The day-by-day log, with every rule written down before its run and every correction, is
[dopamine911/pocket-tank#1](https://github.com/dopamine911/pocket-tank/issues/1).

## Outcome

| | shipped 14M | **candidate 3 (this PR)** |
|---|---|---|
| shape | dim 384, 8 layers, 14.2M params | dim 256, 6 layers, 8 heads, 4.8M params |
| size at 4 bits | 7,557,640 B | 2,579,888 B |
| time per decision, round 1.75C | 3.64 s (11.8 tok/s) | **1.47 s** (29.3 tok/s) |
| internal heap / PSRAM free during play (flat) | 35 / 1,227 KB | 62 / 1,675 KB |
| `docs/retrain-v4.md` acceptance bars missed | 6 | 3, all narrowly |

The tokenizer is unchanged: schema 4, the app's `firmware/main/tokenizer.bin`. The model flashes into the model
partition with its trailer (tag `relabel-d256n6`); nothing else changes.

## The three candidates

Each candidate is the same 4.8M shape; only the training data changed, one step at a time. Candidate 3 is the one in
this PR. The other two are on the source branch with their full records.

| | shipped 14M | candidate 1 | candidate 2 | **candidate 3** |
|---|---|---|---|---|
| data | (yours) | 26B + 31B labels, 50/50, with no-food coverage | + 2,250 dart states labelled by a third teacher | + the 26B relabels the 31B's eating when fed |
| panel rows (student probe, panel seeds 11 / 23 / 37) | misses F1, F4, F6 | misses F3 (dart) | all pass | all pass |
| agreement with the 26B (>= 72%) | 68% | 71% | 74% | 75% |
| bubbles kept at bored 0 / 1 (>= 0.4) | 0.21 / 0.20 | 0.89 / 0.85 | 0.84 / 0.36 | 0.59 / 0.51 |
| dart cliff, bold 0 -> 9 (v3m 0.40) | 0.19 | 0.01 | 0.46 | 0.15 |
| fed, food near: seek_food (F14, report only) | 0.15 | 0.71 | 0.65 | 0.27 |
| pendant: fed fish with food in view eat | 2 / 38 | 16 / 56 | 18 / 70 | 9 / 61 |
| pendant: dart decisions (by timid fish) | 4 / 210 (1) | 6 / 111 (0) | 9 / 149 (4) | 12 / 147 (0) |
| acceptance bars missed (counted the same way) | 6 | 5 | 4 | 3 |

What each step changed:
- **Candidate 1:** already matched the 14M on most rows, at a third of the size. It lost dart, and it ate with fed
  fish, which it learned from the 31B's labels.
- **Candidate 2:** fixed dart, at the cost of keeping a pastime at bored 1.
- **Candidate 3:** halved the eating when fed and brought pastimes back. Its dart cliff fell again, though the panel's
  dart rows still pass at every hunger.

## Upstream's acceptance checks on candidate 3 (`docs/retrain-v4.md`)

Both models' 4-bit files. **Bold** = misses the bar.

| check (bar) | shipped 14M | candidate 3 |
|---|---|---|
| teacher agreement, 26B (>= 72%), n=300 | **68%** | 75% |
| teacher agreement, 31B, n=300 | 58% | 74% |
| bubbles kept at bored 0 / 1 (>= 0.4) | **0.21 / 0.20** | 0.59 / 0.51 |
| ... dropped at bored 8-9 (<= 0.15), explore rises | 0.00, 1.00 | 0.00, 0.99-1.00 |
| social 8, bored 9 leaves the friend | follow 0.32, explore 0.61 | follow 0.01, explore 0.98 |
| night + bored 9 rests / starving + bored 9 eats (>= 0.85) | 0.99 / 0.97 | 1.00 / 0.96 |
| follow cliff, social 0 -> 9 (v3m 0.01 -> 0.52) | 0.05 -> 0.54 | 0.00 -> 0.55 |
| dart cliff, bold 0 -> 9 (v3m 0.02 -> 0.40) | 0.03 -> **0.19** | 0.00 -> **0.15** |
| `fishsim --selftest-llm`, 1 min x3: landmark (< 59%) | 58 / 54 / **64** | 30 / 43 / 31 |
| ... longest one-goal stretch (< 59 s) | **59** / 54 / **59** | 36 / **60** / 36 |
| ... zones per fish-minute (> 1.5) / mean bored (< 3.3) | 2.8-3.5 / 1.7-1.9 | 2.8-3.2 / 1.3-1.6 |
| `--selftest-llm 10` x2: landmark / longest / bored | **59%** / **256 s** / **4.5** | 58% / **87 s** / **3.5** |

How these were run:
- **Agreement:** `eval.py` with the student greedy through `runq4`, n=300 (about ±2.6 points), against our teachers
  on llama.cpp, not `gemma4:26b` on Ollama.
- **Probes:** run on a checkpoint rebuilt from the 4-bit file. On candidate 1 it matched the fp32 checkpoint to within
  0.03.
- **Dart cliff:** it averages 6 hand-written states and swings by training seed: candidate 3's seeds 1 / 2 / 3 give
  0.15 / 0.35 / 0.28. Seed 1 is in this PR because the harness picked it.
- **Census:** the 1-minute runs are noisy (three runs of one model differ by up to 25 points), hence the 10-minute
  runs. The bars were written for 1-minute runs.

## Known differences from the shipped model

- **It eats earlier.** With food near, P(seek_food) at hunger 0 -> 8:
  - candidate 3: 0.07 0.54 0.10 0.20 0.62 0.74 0.85 0.95 0.98
  - shipped: 0.01 0.23 0.05 0.14 0.33 0.50 0.72 0.98 0.99
- **It darts more with bold fish.** On 569 rested, fed, no-food sim states with a wall in view: 0.097 vs 0.059 (the
  teachers' own labels: 0.044). Timid fish dart about as rarely as with the shipped model.
- **The dart cliff misses the v3m bar,** as the shipped model's does.
- **10-minute census:** longest stretch 87 s, mean bored 3.5 (shipped: 256 s, 4.5).

## How candidate 3 was produced

**Teachers.** Your prompt, unchanged (`system_prompt()` sha256 `eb8c0717…`).
- Models: Gemma 4 26B-A4B and Gemma 4 31B (Google's QAT Q4_0 GGUFs), served by llama.cpp b12020 through its
  OpenAI-compatible API. Qwen3.8-Flash-Next (UD-IQ4_XS) labels one shard (step 3).
- Settings: T 0.7, one request at a time.
- Seeds: every label is seeded from the run's base seed, its position and the state
  (`sha256(f"{base}|{index}|{state}")[:4] & 0x7fffffff`, sent as the request's seed). With one worker on the same
  GPU type, a rerun repeats every answer (450 / 450 measured); with 4 workers or another GPU type, about 1% flip.

**Data:** `fish-v4-mix-cov-bigplay-relabel`, 28,948 pairs, sha256 `f16bd193…`. Each step was measured before the next:

1. **26B and 31B labels, 50/50,** from your sim with your prompt.
   - The 26B is balanced and social, but its students don't follow: F1 0.05 on states with no food in view, which
     were only 4% of the data.
   - The 31B follows and is steady, but eats with fed fish: 77% at hunger 1-3 with food near, against 34%.
2. **No-food coverage:** shards where 60% of samples have the pellets cleared first. No-food states went from about 4%
   to 25% of the data.
3. **Dart states:** 2,250 samples where 60% become a rested (energy 7-9), fed (hunger 0-3), daytime fish with no food
   in view, at every boldness.
   - On such states the 26B / 31B dart with 1.4% / 7.5% of bold fish; training on their labels made dart worse.
   - Qwen3.8-Flash-Next darted with 23% of bold fish and 0 of 80 timid ones, so it labelled this shard.
   - No teacher ever labelled a timid fish darting.
4. **Relabel:** the 31B's 4,021 pairs at hunger 1-3 with food in view, answered again by the 26B. seek_food in those
   pairs went from about 58% to 17%; every other pair stayed the same, and so did the count. Hunger 0 (the teachers
   disagree in both directions) and hunger 4+ (a hungry fish should eat) were left alone.

**Training.**
- Your `train.py` (llama2.c) with one new option, `--loss decision`: loss on the decision tokens only.
- 5,000 iterations, batch 64, lr 6e-4. Three seeds; the harness picked seed 1, kept at iteration 4,000.
- ROCm PyTorch in a container, on an AMD Radeon 8060S.
- **Why this shape:** a size sweep (6 seeds per size, the same data and settings) found dim 256 x 6 layers the
  smallest that matched the 14M on every panel row. dim 256 x 4 layers lost the boredom rows (F8, F9); dim 192 x 4
  layers lost F1 and F3.

**Repeating it** (all on the source branch):
1. `run_teacher_jobs.sh` regenerates the labels from the seeds listed in `model/harness/datasets.toml`; `relabel.py`
   does step 4.
2. `python3 model/harness.py run fish-d256-n6-decision-relabel` trains. It checks the folded data against the pinned
   sha256 and stops on a mismatch.
3. `tools/model_trailer.py --model model_q4.bin --out model_trailer.bin --tag relabel-d256n6` makes the trailer; it
   rebuilds byte for byte.

The exact commands and every result file are in that branch's `model/candidates/relabel-d256n6/README.md`.

## Two things we noticed in the checks

These hold whatever you decide about this model.

1. **The bold cases' hunger is drawn once per panel.** `add("bold9", 40, bold=9, energy=9, hunger=rng.randint(0, 2))`
   evaluates `randint` once, so a panel's 40 (or 400) bold states share one hunger value. Which one depends on the seed
   and on `n`: seed 11 is hunger 1 at n=40 and hunger 0 at n=400. A teacher's F3 can swing from 0.04 to 0.82 between
   hunger values.
2. **Every panel state says `wall clear`;** 299 of about 71,500 sim states do (0.4%). F3 asks about a fish in open
   water, which the sim rarely produces.

## Trying it on a pendant

The candidate goes into the model partition; the app and the saved tank are not touched. Back the partition up
first, because the backup holds the model and its trailer:

```
python3 -m esptool --chip esp32s3 -p PORT -b 460800 read_flash 0x290000 0x800000 model-backup.bin
python3 -m esptool --chip esp32s3 -p PORT -b 460800 --after no_reset write_flash 0x290000 model/candidates/relabel-d256n6/model_q4.bin
python3 -m esptool --chip esp32s3 -p PORT -b 460800 write_flash 0xA8F000 model/candidates/relabel-d256n6/model_trailer.bin
# restore: write_flash 0x290000 model-backup.bin
```

To ship it instead:
1. Copy it over `model/out/model_q4.bin`.
2. Set `PT_MODEL_TAG` in `common/version.h` to `relabel-d256n6`.
3. Update the size in `docs/memory_budget.md`.
