# Ladder (open geometry) results — synthetic inventory

| Order | Design | Policy | New timber (m) | ±95 % CI | Reclaimed share | Waste (m) | Components with any new timber |
|---|---|---|---|---|---|---|---|
| random | fixed design | rule (tight fit + geometry) | 3.25 | 0.66 | 85.8 % | 30.2 | 88 % |
| random | fixed design | look-ahead | 1.05 | 0.40 | 95.4 % | 24.3 | 52 % |
| random | fixed design | offline optimum | 0.38 | 0.22 | 98.3 % | 19.9 | 28 % |
| random | open geometry | rule (tight fit + geometry) | 2.25 | 0.61 | 89.0 % | 29.9 | 67 % |
| random | open geometry | buffered rule | 1.24 | 0.35 | 94.1 % | 24.8 | 63 % |
| random | open geometry | look-ahead | 0.57 | 0.27 | 97.1 % | 20.9 | 30 % |
| random | open geometry | offline optimum | 0.11 | 0.12 | 99.5 % | 10.0 | 7 % |
| batch | fixed design | rule (tight fit + geometry) | 6.57 | 0.65 | 71.4 % | 34.1 | 100 % |
| batch | fixed design | look-ahead | 3.18 | 0.56 | 86.2 % | 28.9 | 93 % |
| batch | fixed design | offline optimum | 0.38 | 0.22 | 98.3 % | 19.9 | 28 % |
| batch | open geometry | rule (tight fit + geometry) | 3.27 | 0.60 | 83.6 % | 30.5 | 93 % |
| batch | open geometry | buffered rule | 2.28 | 0.50 | 88.8 % | 27.7 | 78 % |
| batch | open geometry | look-ahead | 1.41 | 0.38 | 92.8 % | 24.0 | 68 % |
| batch | open geometry | offline optimum | 0.11 | 0.12 | 99.5 % | 10.0 | 7 % |

Paired (random): greedy rule minus look-ahead = 1.68 ± 0.48 m; look-ahead better in 39 of 60 streams, worse in 1.

Paired (batch): greedy rule minus look-ahead = 1.87 ± 0.43 m; look-ahead better in 53 of 60 streams, worse in 2.

## Sweep: best_fraction (random order)

| best_fraction | fixed · rule | open · rule | open · buffered | open · look-ahead | open · offline |
|---|---|---|---|---|---|
| 0.05 | 6.38 | 4.44 | 3.01 | 1.97 | 0.45 |
| 0.1 | 5.00 | 3.48 | 2.19 | 1.36 | 0.21 |
| 0.15 | 3.25 | 2.25 | 1.24 | 0.57 | 0.11 |
| 0.25 | 1.92 | 1.47 | 0.56 | 0.27 | 0.03 |

## Sweep: batch_size (random order)

| batch_size | fixed · rule | open · rule | open · buffered | open · look-ahead | open · offline |
|---|---|---|---|---|---|
| 35 | 7.49 | 5.23 | 3.62 | 2.48 | 1.04 |
| 45 | 3.25 | 2.25 | 1.24 | 0.57 | 0.11 |
| 60 | 1.21 | 0.74 | 0.45 | 0.25 | 0.01 |
