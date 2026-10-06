# Result: cached half trace held

Ratios are incumbent/candidate complete `pointFromX` times. All outputs
matched exactly. Cold batches include construction of the candidate's
half-trace image table.

| Degree | Cold 64 primary / confirm | Cold 256 primary / confirm | Cold 1024 primary / confirm | Warm 256 primary / confirm |
| ---: | ---: | ---: | ---: | ---: |
| 11 | 1.18 / 1.43x | 1.51 / 1.58x | 1.57 / 1.56x | 1.53 / 1.60x |
| 15 | 1.43 / 1.41x | 1.67 / 1.55x | 1.63 / 1.65x | 1.64 / 1.63x |
| 53 | 0.74 / 0.64x | 1.57 / 1.61x | 2.60 / 2.56x | 2.97 / 3.09x |
| 131 | 0.27 / 0.28x | 0.92 / 1.03x | 2.59 / 2.68x | 5.76 / 6.03x |

The setup cost depends strongly on field degree and workload size. The
degree-131 cold 256-point result does not reproducibly beat the incumbent.
This pilot therefore makes no speedup claim for automatic point recovery or
for a complete index-calculus run.
