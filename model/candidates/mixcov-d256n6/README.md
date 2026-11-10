# Candidate: fish-d256-n6-decision on fish-v4-mix-cov, seed 2 (issue #1)

A 4.8M-parameter fish model (2.6 MB at 4 bits), a third the size of the shipped 14M (7.6 MB).
**A test candidate, not a replacement:** `model/out/model_q4.bin` is still the shipped model, and the
harness marks this file "it still FAILS a row: do not ship" (F3 below).

| File | What |
|---|---|
| `model_q4.bin` | the model, 2,579,888 B, dim 256, 6 layers, 8 heads, schema 4 (the shipped tokenizer) |
| `model_trailer.bin` | its trailer, tag `mixcov-d256n6` (`tools/model_trailer.py`) |
| `SHA256SUMS` | checksums of both |
| `run/` | the harness record: `manifest.json` (git sha, dataset sha, image, card), `result.json`, `train.log`, both probes, the run's `report.md` (all 3 seeds) |
| `pendant/` | serial logs from the 1.75C round pendant, same board, 2026-11-10: this model and the stock 14M |

## How it was made

- **Labels:** Gemma 4 26B-A4B and 31B (Google QAT Q4_0 files) on llama.cpp b12020 (Vulkan, Radeon AI PRO R9700), upstream prompt unchanged,
  T 0.7, seeded labels, one request at a time. Half from each teacher; about a quarter of the sim states
  have the pellets cleared (`gen_traces.py --no-food 0.6` shards) so following and darting get labels.
- **Dataset:** `fish-v4-mix-cov` in `harness/datasets.toml`, 26,698 pairs, sha256 `d76fd64a…`.
- **Training:** `harness/runs/fish-d256-n6-decision-mixcov.toml`: 5,000 iterations, batch 64, lr 6e-4,
  loss on the decision tokens only, seeds 1-3; this is seed 2 (the harness's pick), kept at iteration 3,200.
  Commit `dd01e751`, image `pt-train-rocm:gfx120X`, Radeon AI PRO R9700, 2 min.
- **Repeat:** `python3 harness.py run fish-d256-n6-decision-mixcov` (needs the label files under
  `out/data/`, which are not in git; `run_teacher_jobs.sh` regenerates them from the same seeds, and with
  one worker on the same GPU type the labels repeat exactly). Then
  `python3 ../tools/model_trailer.py --model model_q4.bin --out model_trailer.bin --tag mixcov-d256n6`
  (rebuilt byte for byte on 2026-11-10).

## Checks (prompt_check v4 panel rows, student probe n=400, panel seeds 11 / 23)

| Row (bar) | this seed | 3-seed mean |
|---|---|---|
| F1 follow, social 9 (>= 0.40) | 0.665 / 0.659 | 0.645 |
| F2 (<= 0.05) | 0.024 / 0.025 | 0.017 |
| **F3 dart, bold 9 (>= 0.10)** | **0.077 / 0.047 (fails)** | 0.127 |
| F4 timid dart (<= 0.03) | 0.016 / 0.014 | 0.032 |
| F5 (>= 0.95) | 0.998 / 0.998 | 0.997 |
| F6 (<= 0.05) | 0.020 / 0.026 | 0.025 |
| F7 (<= 0.15) | 0.000 / 0.001 | 0.001 |
| F8 (>= 0.25) | 0.984 / 0.980 | 0.973 |
| F9 (<= 0.15) | 0.007 / 0.007 | 0.010 |
| F10 (>= 0.40) | 0.717 / 0.715 | 0.753 |
| F11 (>= 0.70) | 0.948 / 0.946 | 0.931 |
| F12 (== 0) | 0.000 / 0.000 | 0.000 |
| F13 (< 0.45) | 0.374 / 0.366 | 0.373 |

## On the pendant (same board, same day; `python3 pendant_stats.py pendant/pendant-4.8m.log pendant/pendant-stock.log`)

| | stock 14M | this model |
|---|---|---|
| log | 16.1 min, 3 fish | 12.5 min, 2-3 fish |
| time per decision, median (range) | 3,644 ms (3,583-4,124) | 1,474 ms (1,220-1,604) |
| tokens/s | 11.8 | 29.8 |
| internal heap free | 35 KB, flat | 62 KB, flat |
| PSRAM free | 1,227 KB, flat | 1,669 KB, flat |
| asks / decisions | 259 / 209 | 119 / 119 |
| I2C "transaction failed" pairs | 18 | 18 (so not the model) |
| fed (hunger 0-2), food in view: seek_food | 2 of 38 | 16 of 56 |

2.5x faster per decision. Asks for a fish already waiting are folded into one (`g_pending`,
`firmware/main/advisor_llm_esp.c`): with the stock model 50 of 259 were, with this model none.
Behaviour is not a controlled comparison (different tank states); it eats more when not hungry,
which matches its labels (the 31B half eats more) and is not one of the bars.

## Flash and restore (round 1.75C, aquarium firmware; the app and the saved tank are not touched)

```
python3 -m esptool --chip esp32s3 -p /dev/ttyACM0 -b 460800 read_flash 0x290000 0x800000 model-backup.bin
python3 -m esptool --chip esp32s3 -p /dev/ttyACM0 -b 460800 --after no_reset write_flash 0x290000 model_q4.bin
python3 -m esptool --chip esp32s3 -p /dev/ttyACM0 -b 460800 write_flash 0xA8F000 model_trailer.bin
# restore: write_flash 0x290000 model-backup.bin (the backup holds the model and its trailer)
```
