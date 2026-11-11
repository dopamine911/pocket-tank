# Upstream's acceptance checks: stock 14M vs this 4.8M (2026-11-10)

The four checks in `docs/retrain-v4.md` ("Acceptance (morning)"), run on both 4-bit device files:
stock = `model/out/model_q4.bin` (sha256 50bed3e1…, 14.2M), 4.8M = `../model_q4.bin` (72fa241c…).
**Bold** = misses upstream's bar.

## 1. Teacher agreement (bar >= 72%)

`eval.py --schema 4 --count 300 --seed 1 --teacher --api openai --label-seed 7 --run-bin ./runq4`
(`run_agreement.sh`). The student is the 4-bit file through `runq4`, greedy (`-t 0`, as eval.py does). The sim
is closed-loop (each student's choice changes the next states), so the two models see different states.
Upstream used n=60 and gemma4:26b on Ollama; here n=300 (+-2.6 points), Gemma 4 26B-A4B and 31B (Google QAT
Q4_0) on llama.cpp b12020.

| teacher | stock | 4.8M |
|---|---|---|
| 26B (upstream's teacher model) | **68%** (first 60: 31/60) | **71%** (37/60) |
| 31B | **58%** (32/60) | 73% (39/60) |

## 2. Probe (`probe_dist.py --schema 4 --device cuda`, from `q4_to_ckpt.py`'s checkpoints)

| upstream's wording | stock | 4.8M |
|---|---|---|
| bored sweep at the bubbles: P(bubbles again) >= 0.4 at bored 0-1 ... | **0.21 / 0.20** | 0.89 / 0.85 |
| ... <= 0.15 at bored 8-9, while P(explore) rises | 0.00 / 0.00, explore 1.00 | 0.00 / 0.00, explore 1.00 |
| social 8 at bored 9 leaves the friend | follow 0.32, explore 0.61 | follow 0.01, explore 0.98 |
| night + bored 9 still rests | 0.99 | 1.00 |
| starving + bored 9 still seeks food (>= 0.85) | 0.97 | 0.95 |
| P(flee_shadow) ~0 everywhere | yes | yes |

Real states (`--data`: 1,000 held-out labels, 500 from each teacher, sim seed 1, in neither model's
training): teacher label == greedy 58% (stock) vs 75% (4.8M); in top-2 80% vs 93%.

## 3. Personality cliffs, no worse than v3m (follow 0.01 -> 0.52, dart 0.02 -> 0.40)

| | stock | 4.8M |
|---|---|---|
| P(follow) social 0 -> 9 | 0.05 -> 0.54 | 0.01 -> 0.82 |
| P(dart) bold 0 -> 9 | **0.03 -> 0.19** | **0.00 -> 0.01** |

## 4. Sim census (`sim/fishsim --selftest-llm`, built by `../../../docker/Dockerfile.sim`)

Upstream's bars: landmark time under 59%, distinct zones per fish-minute above 1.5, longest one-goal
stretch under 59 s, mean bored under 3.3. The default run is 60 sim-seconds (3 runs each); a 60 s run makes
the 59 s bar nearly automatic, so 10-minute runs (`--selftest-llm 10`, 2 each) are below too.

| | stock 1 min (3 runs) | 4.8M 1 min (3 runs) | stock 10 min (2 runs) | 4.8M 10 min (2 runs) |
|---|---|---|---|---|
| landmark time | 58 / 54 / **64%** | **70 / 70** / 45% | **59** / 54% | 54 / 54% |
| zones per fish-minute | 3.2 / 3.5 / 2.8 | 1.8 / 1.8 / 2.5 | 3.0 / 3.2 | 3.4 / 3.4 |
| longest one-goal stretch | **59** / 54 / **59 s** | **60 / 60** / 30 s | **256 / 261 s** | **82 / 82 s** |
| mean bored | 1.7 / 1.7 / 1.9 | 2.5 / 2.5 / 1.7 | **4.5 / 4.7** | **4.2 / 4.2** |

The 4.8M's runs 1 and 2 came out identical (1 and 10 minutes); the stock model's did not. Not explained.
Each sim runs from a scratch folder `census-<model>/sim` whose `../model/out/` holds that model and the
shipped tokenizer (the sim reads that fixed path).

## Files

`agree-<teacher>-<model>.txt`, `probe_dist-<model>.txt`, `census-<model>-r<N>.txt` (1 min),
`census10-<model>-r<N>.txt` (10 min).
