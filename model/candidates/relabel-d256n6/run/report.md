# Run fish-d256-n6-decision-relabel

model fish-d256-n6, dataset fish-v4-mix-cov-bigplay-relabel (sha256 f16bd193045b), 5000 iters, batch 64, lr 0.0006, loss decision, mode training; 3/3 seeds collected.

Wall time 3.9 min for 3 jobs (their sum 8.1 min, 2.05x parallel).

Lab in training mode for the whole run: yes, 3.9 min (at start: marvin training, zaphod training).

## Jobs

| seed | card | host | device | s/iter | train / job wall | peak GPU (torch) | card mem peak (sysfs) | val loss | goal NLL | goal acc | kept iter | attempts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | marvin-8060s | marvin | Radeon 8060S Graphics | 0.04 | 3.5 / 3.6 min | 631 MiB | 1465 MiB (before 17) | 8.0092 | 0.5767 | 0.776 | 4000 | 1 |
| 2 | zaphod-card2 | zaphod | AMD Radeon AI PRO R9700 | 0.02 | 2.0 / 2.2 min | 584 MiB | 5192 MiB (before 3824) | 8.6947 | 0.6301 | 0.757 | 4600 | 1 |
| 3 | zaphod-card1 | zaphod | AMD Radeon AI PRO R9700 | 0.02 | 2.1 / 2.3 min | 584 MiB | 9080 MiB (before 7713) | 7.6163 | 0.6182 | 0.758 | 5000 | 1 |

goal NLL / acc: on the job's held-out docs, the label goal under the device's softmax over the goal tokens only, and how often its top goal is the label (the teacher's own repeat agreement bounds it).

torch 2.10.0+rocm7.13.0a20260513 (HIP 7.13.26183); git {'sha': 'e888a5b1e7628f8ccc276348d005ca2055971a9d', 'dirty': False}

## Rows by seed and panel

| row (limit) | s1 p11 / p23 | s2 p11 / p23 | s3 p11 / p23 | mean | sd seeds | panel spread | min margin (scaled) |
|---|---|---|---|---|---|---|---|
| F1 (>= 0.40) | 0.598 / 0.597 | 0.658 / 0.675 | 0.716 / 0.711 | 0.659 | 0.058 | 0.008 | +0.197 (+0.33) |
| F2 (<= 0.05) | 0.007 / 0.006 | 0.018 / 0.016 | 0.002 / 0.002 | 0.008 | 0.008 | 0.001 | +0.032 (+0.64) |
| F3 (>= 0.10) | 0.370 / 0.251 | 0.217 / 0.290 | 0.499 / 0.411 | 0.340 | 0.104 | 0.093 | +0.117 (+0.13) |
| F4 (<= 0.03) | 0.007 / 0.006 | 0.002 / 0.002 | 0.001 / 0.001 | 0.003 | 0.003 | 0.000 | +0.023 (+0.76) |
| F5 (>= 0.95) | 0.993 / 0.993 | 0.996 / 0.996 | 0.993 / 0.989 | 0.994 | 0.003 | 0.001 | +0.039 (+0.79) |
| F6 (<= 0.05) | 0.004 / 0.003 | 0.004 / 0.004 | 0.002 / 0.004 | 0.003 | 0.001 | 0.001 | +0.046 (+0.92) |
| F7 (<= 0.15) | 0.003 / 0.003 | 0.002 / 0.001 | 0.002 / 0.002 | 0.002 | 0.001 | 0.000 | +0.147 (+0.98) |
| F8 (>= 0.25) | 0.873 / 0.869 | 0.947 / 0.947 | 0.970 / 0.970 | 0.929 | 0.052 | 0.002 | +0.619 (+0.83) |
| F9 (<= 0.15) | 0.048 / 0.037 | 0.029 / 0.031 | 0.021 / 0.021 | 0.031 | 0.011 | 0.004 | +0.102 (+0.68) |
| F10 (>= 0.40) | 0.473 / 0.490 | 0.664 / 0.664 | 0.664 / 0.687 | 0.607 | 0.109 | 0.013 | +0.073 (+0.12) |
| F11 (>= 0.70) | 0.927 / 0.933 | 0.884 / 0.919 | 0.887 / 0.830 | 0.897 | 0.036 | 0.033 | +0.130 (+0.43) |
| F12 (== 0) | 0.000 / 0.000 | 0.000 / 0.000 | 0.000 / 0.000 | 0.000 | 0.000 | 0.000 | - (-) |
| F13 (< 0.45) | 0.262 / 0.281 | 0.286 / 0.298 | 0.346 / 0.366 | 0.306 | 0.044 | 0.017 | +0.084 (+0.19) |
| F14 (-) | 0.285 / 0.257 | 0.286 / 0.254 | 0.291 / 0.253 | 0.271 | 0.001 | 0.033 | - (-) |
| **smallest scaled margin** | **+0.12** (F10, p11, raw +0.073) | **+0.13** (F3, p11, raw +0.117) | **+0.19** (F13, p23, raw +0.084) | | | | |

sd seeds: the standard deviation of the per-seed means (training-seed variance); panel spread: the mean max - min across one seed's panels (probe sampling noise). A row whose sd seeds is near its min margin can flip on another seed. Scaled: the margin as a share of the row's headroom (limit to best possible: 1 for a rate or a paired difference, 1/9 for the A11 slope, 0 for a <= row); 1 is perfect, 0 the limit.

## Selection

Rule: the widest smallest scaled margin over every limited row and panel. Seeds within 0.104 of the widest are tied (the binding rows' scaled panel spread, at least 0.005) and go to the lower goal NLL.

1. seed 3: smallest scaled margin +0.187 on F13, goal NLL 0.6182, all rows pass, tied for best
2. seed 2: smallest scaled margin +0.130 on F3, goal NLL 0.6301, all rows pass, tied for best
3. seed 1: smallest scaled margin +0.122 on F10, goal NLL 0.5767, all rows pass, tied for best  <- selected

Selected: seed 1, `out/harness/fish-d256-n6-decision-relabel/s1/model_q4.bin`

