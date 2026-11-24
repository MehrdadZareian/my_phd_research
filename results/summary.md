# Results summary (synthetic inventory)

## Main comparison

| Order | Policy | New timber (% of length) | ±95 % CI | Waste (m) | Discarded usable | Gap to offline closed vs greedy |
|---|---|---|---|---|---|---|
| random | greedy | 3.88 | 0.76 | 14.07 | 0.00 | 0 % |
| random | tight fit (rule) | 1.30 | 0.51 | 13.29 | 0.00 | 90 % |
| random | buffered tight fit | 1.19 | 0.52 | 10.74 | 0.00 | 94 % |
| random | look-ahead | 1.02 | 0.47 | 10.70 | 0.00 | 100 % |
| random | look-ahead (learned supply) | 1.03 | 0.47 | 10.77 | 0.00 | 100 % |
| random | look-ahead (hindsight) | 1.02 | 0.47 | 10.63 | 0.00 | 100 % |
| random | offline optimum | 1.02 | 0.47 | 9.72 | 0.00 | 100 % |
| batch | greedy | 5.36 | 0.95 | 14.00 | 0.00 | 0 % |
| batch | tight fit (rule) | 1.34 | 0.59 | 13.40 | 0.00 | 92 % |
| batch | buffered tight fit | 1.34 | 0.59 | 10.84 | 0.00 | 92 % |
| batch | look-ahead | 1.19 | 0.53 | 10.78 | 0.00 | 96 % |
| batch | look-ahead (learned supply) | 1.27 | 0.56 | 10.91 | 0.00 | 94 % |
| batch | look-ahead (hindsight) | 1.15 | 0.51 | 10.73 | 0.00 | 97 % |
| batch | offline optimum | 1.02 | 0.47 | 9.72 | 0.00 | 100 % |

## Sweep: buffer

| buffer | greedy | tight fit (rule) | buffered tight fit | look-ahead | offline optimum | look-ahead gap closed |
|---|---|---|---|---|---|---|
| 0 | 4.39 | 1.34 | 1.34 | 1.22 | 1.14 | 97 % |
| 1 | 4.39 | 1.34 | 1.27 | 1.21 | 1.14 | 98 % |
| 2 | 4.39 | 1.34 | 1.35 | 1.14 | 1.14 | 100 % |
| 4 | 4.39 | 1.34 | 1.35 | 1.14 | 1.14 | 100 % |
| 8 | 4.39 | 1.34 | 1.35 | 1.14 | 1.14 | 100 % |

## Sweep: best_fraction

| best_fraction | greedy | tight fit (rule) | buffered tight fit | look-ahead | offline optimum | look-ahead gap closed |
|---|---|---|---|---|---|---|
| 0.05 | 6.66 | 3.89 | 3.62 | 3.22 | 3.22 | 100 % |
| 0.1 | 5.44 | 2.48 | 2.36 | 1.75 | 1.69 | 98 % |
| 0.15 | 4.39 | 1.34 | 1.29 | 1.14 | 1.14 | 100 % |
| 0.25 | 3.07 | 0.53 | 0.47 | 0.47 | 0.47 | 100 % |
| 0.4 | 2.12 | 0.32 | 0.32 | 0.32 | 0.32 | 100 % |

## Sweep: supply_ratio

| supply_ratio | greedy | tight fit (rule) | buffered tight fit | look-ahead | offline optimum | look-ahead gap closed |
|---|---|---|---|---|---|---|
| 1 | 24.81 | 19.98 | 19.73 | 19.19 | 19.16 | 100 % |
| 1.25 | 12.38 | 6.91 | 6.74 | 6.20 | 6.14 | 99 % |
| 1.5 | 4.39 | 1.34 | 1.29 | 1.14 | 1.14 | 100 % |
| 2 | 0.53 | 0.00 | 0.07 | 0.00 | 0.00 | 100 % |
| 2.5 | 0.20 | 0.13 | 0.13 | 0.13 | 0.13 | 100 % |

## Paired difference (main, random order)

Tight-fit rule minus look-ahead: 0.28 ± 0.20 percentage points (look-ahead better in 7 of 100 streams, worse in 0).
