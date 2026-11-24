# Human supply hints — open-geometry ladder (synthetic inventory)

## World A: misleading supply (true short share ≈ 0.8, source statistics say 0.34)

| Strategy | New timber (m) | ±95 % CI | Gain vs no hint (paired) | Better / worse streams | Share of gap to offline closed |
|---|---|---|---|---|---|
| offline optimum | 5.31 | 0.62 | +3.31 ± 0.33 | 40 / 0 | 100 % |
| buffered rule | 9.03 | 0.68 | -0.41 ± 0.33 | 15 / 25 | -12 % |
| look-ahead, no hint | 8.62 | 0.66 | +0.00 ± 0.00 | 0 / 0 | 0 % |
| look-ahead, learned supply | 8.87 | 0.65 | -0.25 ± 0.27 | 13 / 25 | -7 % |
| hint correct (85 % short) | 8.30 | 0.65 | +0.32 ± 0.27 | 25 / 15 | 10 % |
| hint vague ('mostly short', 70 %) | 8.39 | 0.69 | +0.23 ± 0.32 | 19 / 16 | 7 % |
| hint exaggerated (95 % short) | 8.40 | 0.72 | +0.22 ± 0.34 | 24 / 15 | 7 % |
| hint wrong ('mostly long', 20 %) | 9.00 | 0.69 | -0.38 ± 0.27 | 10 / 27 | -11 % |
| hint vague + update | 8.49 | 0.66 | +0.13 ± 0.32 | 21 / 17 | 4 % |
| hint wrong + update | 8.63 | 0.68 | -0.01 ± 0.33 | 17 / 19 | -0 % |
| perfect supply model | 8.36 | 0.64 | +0.26 ± 0.28 | 21 / 18 | 8 % |
| clairvoyant look-ahead | 7.94 | 0.63 | +0.68 ± 0.32 | 30 / 10 | 21 % |
| look-ahead, no hint, buffer 8 | 7.61 | 0.59 | +1.01 ± 0.35 | 32 / 8 | 31 % |
| buffered rule, buffer 8 | 7.72 | 0.59 | +0.90 ± 0.31 | 31 / 9 | 27 % |

## World B: normal supply (true short share ≈ 0.35)

| Strategy | New timber (m) | ±95 % CI | Gain vs no hint (paired) | Better / worse streams | Share of gap to offline closed |
|---|---|---|---|---|---|
| offline optimum | 0.14 | 0.12 | +0.50 ± 0.27 | 13 / 0 | 100 % |
| buffered rule | 1.55 | 0.52 | -0.92 ± 0.35 | 2 / 25 | -184 % |
| look-ahead, no hint | 0.64 | 0.35 | +0.00 ± 0.00 | 0 / 0 | 0 % |
| hint wrong ('mostly short', 80 %) | 0.76 | 0.40 | -0.13 ± 0.20 | 5 / 8 | -25 % |
| hint wrong + update | 0.52 | 0.29 | +0.12 ± 0.20 | 8 / 5 | 24 % |
