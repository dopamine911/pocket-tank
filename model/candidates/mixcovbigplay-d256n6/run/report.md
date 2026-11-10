# Run fish-d256-n6-decision-mixcovbigplay

model fish-d256-n6, dataset fish-v4-mix-cov-bigplay (sha256 a52e8648dd8a), 5000 iters, batch 64, lr 0.0006, loss decision, mode training; 3/3 seeds collected.

Wall time 3.9 min for 3 jobs (their sum 8.0 min, 2.04x parallel).

Lab in training mode for the whole run: yes, 3.9 min (at start: marvin training, zaphod training).

## Jobs

| seed | card | host | device | s/iter | train / job wall | peak GPU (torch) | card mem peak (sysfs) | val loss | goal NLL | goal acc | kept iter | attempts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | marvin-8060s | marvin | Radeon 8060S Graphics | 0.04 | 3.5 / 3.6 min | 631 MiB | 1465 MiB (before 17) | 8.7056 | 0.5910 | 0.763 | 3600 | 1 |
| 2 | zaphod-card2 | zaphod | AMD Radeon AI PRO R9700 | 0.02 | 2.0 / 2.2 min | 584 MiB | 5192 MiB (before 3824) | 8.3884 | 0.6612 | 0.748 | 4000 | 1 |
| 3 | zaphod-card1 | zaphod | AMD Radeon AI PRO R9700 | 0.02 | 2.1 / 2.3 min | 584 MiB | 9090 MiB (before 7723) | 8.1416 | 0.6308 | 0.751 | 5000 | 1 |

goal NLL / acc: on the job's held-out docs, the label goal under the device's softmax over the goal tokens only, and how often its top goal is the label (the teacher's own repeat agreement bounds it).

torch 2.10.0+rocm7.13.0a20260513 (HIP 7.13.26183); git {'sha': 'cf0175ec287ce00352b38aed7e8b1e5638a97e7e', 'dirty': False}

## Rows by seed and panel

| row (limit) | s1 p11 / p23 | s2 p11 / p23 | s3 p11 / p23 | mean | sd seeds | panel spread | min margin (scaled) |
|---|---|---|---|---|---|---|---|
| F1 (>= 0.40) | 0.606 / 0.608 | 0.716 / 0.726 | 0.737 / 0.753 | 0.691 | 0.074 | 0.009 | +0.206 (+0.34) |
| F2 (<= 0.05) | 0.008 / 0.010 | 0.013 / 0.013 | 0.010 / 0.011 | 0.011 | 0.002 | 0.001 | +0.037 (+0.74) |
| F3 (>= 0.10) | 0.372 / 0.415 | 0.342 / 0.378 | 0.241 / 0.139 | 0.315 | 0.109 | 0.060 | +0.039 (+0.04) |
| F4 (<= 0.03) | 0.011 / 0.010 | 0.011 / 0.012 | 0.086 / 0.082 | 0.035 | 0.042 | 0.002 | -0.056 (-1.85) |
| F5 (>= 0.95) | 0.996 / 0.996 | 0.996 / 0.996 | 0.993 / 0.991 | 0.995 | 0.002 | 0.001 | +0.041 (+0.82) |
| F6 (<= 0.05) | 0.004 / 0.004 | 0.003 / 0.003 | 0.011 / 0.012 | 0.006 | 0.005 | 0.001 | +0.038 (+0.75) |
| F7 (<= 0.15) | 0.001 / 0.001 | 0.002 / 0.002 | 0.004 / 0.004 | 0.002 | 0.002 | 0.000 | +0.146 (+0.97) |
| F8 (>= 0.25) | 0.992 / 0.990 | 0.988 / 0.976 | 0.976 / 0.975 | 0.983 | 0.008 | 0.005 | +0.725 (+0.97) |
| F9 (<= 0.15) | 0.002 / 0.002 | 0.045 / 0.049 | 0.018 / 0.019 | 0.022 | 0.023 | 0.001 | +0.101 (+0.68) |
| F10 (>= 0.40) | 0.572 / 0.605 | 0.589 / 0.605 | 0.552 / 0.545 | 0.578 | 0.026 | 0.018 | +0.145 (+0.24) |
| F11 (>= 0.70) | 0.951 / 0.947 | 0.932 / 0.896 | 0.907 / 0.851 | 0.914 | 0.035 | 0.032 | +0.151 (+0.50) |
| F12 (== 0) | 0.000 / 0.000 | 0.000 / 0.000 | 0.000 / 0.000 | 0.000 | 0.000 | 0.000 | - (-) |
| F13 (< 0.45) | 0.323 / 0.327 | 0.380 / 0.375 | 0.318 / 0.314 | 0.340 | 0.033 | 0.004 | +0.070 (+0.16) |
| F14 (-) | 0.649 / 0.625 | 0.632 / 0.619 | 0.572 / 0.545 | 0.607 | 0.043 | 0.021 | - (-) |
| **smallest scaled margin** | **+0.27** (F13, p23, raw +0.123) | **+0.16** (F13, p11, raw +0.070) | **-1.85** (F4, p11, raw -0.056) | | | | |

sd seeds: the standard deviation of the per-seed means (training-seed variance); panel spread: the mean max - min across one seed's panels (probe sampling noise). A row whose sd seeds is near its min margin can flip on another seed. Scaled: the margin as a share of the row's headroom (limit to best possible: 1 for a rate or a paired difference, 1/9 for the A11 slope, 0 for a <= row); 1 is perfect, 0 the limit.

## Selection

Rule: the widest smallest scaled margin over every limited row and panel. Seeds within 0.059 of the widest are tied (the binding rows' scaled panel spread, at least 0.005) and go to the lower goal NLL.

1. seed 1: smallest scaled margin +0.273 on F13, goal NLL 0.5910, all rows pass, tied for best  <- selected
2. seed 2: smallest scaled margin +0.156 on F13, goal NLL 0.6612, all rows pass
3. seed 3: smallest scaled margin -1.851 on F4, goal NLL 0.6308, a row FAILS

Selected: seed 1, `out/harness/fish-d256-n6-decision-mixcovbigplay/s1/model_q4.bin`

