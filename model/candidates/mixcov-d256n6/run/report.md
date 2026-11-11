# Run fish-d256-n6-decision-mixcov

model fish-d256-n6, dataset fish-v4-mix-cov (sha256 d76fd64adfba), 5000 iters, batch 64, lr 0.0006, loss decision, mode training; 3/3 seeds collected.

Wall time 3.9 min for 3 jobs (their sum 8.1 min, 2.07x parallel).

Lab in training mode for the whole run: yes, 3.9 min (at start: marvin training, zaphod training).

## Jobs

| seed | card | host | device | s/iter | train / job wall | peak GPU (torch) | card mem peak (sysfs) | val loss | goal NLL | goal acc | kept iter | attempts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | marvin-8060s | marvin | Radeon 8060S Graphics | 0.04 | 3.5 / 3.6 min | 631 MiB | 1465 MiB (before 17) | 8.4053 | 0.5911 | 0.753 | 3200 | 1 |
| 2 | zaphod-card2 | zaphod | AMD Radeon AI PRO R9700 | 0.02 | 2.0 / 2.2 min | 584 MiB | 5192 MiB (before 3824) | 8.8816 | 0.5513 | 0.779 | 3200 | 1 |
| 3 | zaphod-card1 | zaphod | AMD Radeon AI PRO R9700 | 0.02 | 2.1 / 2.3 min | 584 MiB | 9090 MiB (before 7723) | 8.9513 | 0.5736 | 0.774 | 4400 | 1 |

goal NLL / acc: on the job's held-out docs, the label goal under the device's softmax over the goal tokens only, and how often its top goal is the label (the teacher's own repeat agreement bounds it).

torch 2.10.0+rocm7.13.0a20260513 (HIP 7.13.26183); git {'sha': 'dd01e751ee38f9cc55f4c7a7b6ce864c06a76849', 'dirty': False}

## Rows by seed and panel

| row (limit) | s1 p11 / p23 | s2 p11 / p23 | s3 p11 / p23 | mean | sd seeds | panel spread | min margin (scaled) |
|---|---|---|---|---|---|---|---|
| F1 (>= 0.40) | 0.598 / 0.580 | 0.665 / 0.659 | 0.673 / 0.693 | 0.645 | 0.049 | 0.014 | +0.180 (+0.30) |
| F2 (<= 0.05) | 0.015 / 0.015 | 0.024 / 0.025 | 0.011 / 0.012 | 0.017 | 0.007 | 0.001 | +0.025 (+0.49) |
| F3 (>= 0.10) | 0.225 / 0.083 | 0.077 / 0.047 | 0.266 / 0.063 | 0.127 | 0.056 | 0.125 | -0.053 (-0.06) |
| F4 (<= 0.03) | 0.002 / 0.003 | 0.016 / 0.014 | 0.076 / 0.078 | 0.032 | 0.040 | 0.002 | -0.048 (-1.62) |
| F5 (>= 0.95) | 0.997 / 0.997 | 0.998 / 0.998 | 0.997 / 0.995 | 0.997 | 0.001 | 0.001 | +0.045 (+0.91) |
| F6 (<= 0.05) | 0.048 / 0.051 | 0.020 / 0.026 | 0.002 / 0.003 | 0.025 | 0.024 | 0.003 | -0.001 (-0.03) |
| F7 (<= 0.15) | 0.003 / 0.002 | 0.000 / 0.001 | 0.001 / 0.001 | 0.001 | 0.001 | 0.000 | +0.147 (+0.98) |
| F8 (>= 0.25) | 0.953 / 0.955 | 0.984 / 0.980 | 0.984 / 0.984 | 0.973 | 0.017 | 0.002 | +0.703 (+0.94) |
| F9 (<= 0.15) | 0.013 / 0.011 | 0.007 / 0.007 | 0.012 / 0.012 | 0.010 | 0.003 | 0.001 | +0.137 (+0.91) |
| F10 (>= 0.40) | 0.733 / 0.728 | 0.717 / 0.715 | 0.818 / 0.809 | 0.753 | 0.052 | 0.006 | +0.315 (+0.52) |
| F11 (>= 0.70) | 0.942 / 0.940 | 0.948 / 0.946 | 0.912 / 0.900 | 0.931 | 0.022 | 0.005 | +0.200 (+0.67) |
| F12 (== 0) | 0.000 / 0.000 | 0.000 / 0.000 | 0.000 / 0.000 | 0.000 | 0.000 | 0.000 | - (-) |
| F13 (< 0.45) | 0.362 / 0.367 | 0.374 / 0.366 | 0.383 / 0.389 | 0.373 | 0.011 | 0.006 | +0.061 (+0.14) |
| F14 (-) | 0.600 / 0.575 | 0.737 / 0.697 | 0.585 / 0.561 | 0.626 | 0.079 | 0.030 | - (-) |
| **smallest scaled margin** | **-0.03** (F6, p23, raw -0.001) | **-0.06** (F3, p23, raw -0.053) | **-1.62** (F4, p23, raw -0.048) | | | | |

sd seeds: the standard deviation of the per-seed means (training-seed variance); panel spread: the mean max - min across one seed's panels (probe sampling noise). A row whose sd seeds is near its min margin can flip on another seed. Scaled: the margin as a share of the row's headroom (limit to best possible: 1 for a rate or a paired difference, 1/9 for the A11 slope, 0 for a <= row); 1 is perfect, 0 the limit.

## Selection

Rule: the widest smallest scaled margin over every limited row and panel. Seeds within 0.138 of the widest are tied (the binding rows' scaled panel spread, at least 0.005) and go to the lower goal NLL.

1. seed 1: smallest scaled margin -0.025 on F6, goal NLL 0.5911, a row FAILS, tied for best
2. seed 2: smallest scaled margin -0.059 on F3, goal NLL 0.5513, a row FAILS, tied for best  <- selected
3. seed 3: smallest scaled margin -1.616 on F4, goal NLL 0.5736, a row FAILS

Selected: seed 2, `out/harness/fish-d256-n6-decision-mixcov/s2/model_q4.bin` (it still FAILS a row: do not ship)

