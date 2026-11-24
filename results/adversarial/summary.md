# Adversarial tests — open-geometry ladder (synthetic inventory)

| Test | Greedy rule | Buffered rule | Look-ahead | Look-ahead (learned supply) | Offline optimum |
|---|---|---|---|---|---|
| Random order | 1.82 ± 0.66 | 1.06 ± 0.43 | 0.55 ± 0.30 |  | 0.12 ± 0.11 |
| Long pieces first | 1.50 ± 0.57 | 1.15 ± 0.40 | 1.08 ± 0.34 |  | 0.12 ± 0.11 |
| Short pieces first | 2.83 ± 0.70 | 1.34 ± 0.41 | 0.65 ± 0.35 |  | 0.12 ± 0.11 |
| Best class first | 2.56 ± 0.72 | 1.82 ± 0.51 | 0.97 ± 0.37 |  | 0.12 ± 0.11 |
| Best class last | 2.47 ± 0.68 | 1.29 ± 0.53 | 0.86 ± 0.47 |  | 0.12 ± 0.11 |
| Random order (search batches) | 2.38 ± 1.04 | 1.28 ± 0.70 | 0.65 ± 0.48 |  | 0.12 ± 0.17 |
| Worst order found by search | 4.68 ± 1.23 | 3.00 ± 0.84 | 1.10 ± 0.60 |  | 0.12 ± 0.17 |
| Misleading supply (mostly short pieces) | 11.72 ± 0.60 | 9.31 ± 0.50 | 8.97 ± 0.56 | 9.19 ± 0.48 | 5.48 ± 0.43 |

Search adversary, increase from random to worst order found (m):
- greedy rule: +2.30 m (worst single batch 11.24 m)
- buffered rule: +1.72 m (worst single batch 6.82 m)
- look-ahead: +0.44 m (worst single batch 4.02 m)
