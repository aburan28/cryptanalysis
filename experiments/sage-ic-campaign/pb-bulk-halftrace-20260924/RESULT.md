# Result: explicit bulk half trace

All eight cells returned identical factor-base points and Frobenius orbits.
Ratios below are paired median times for complete cold `factorBase` calls,
including half-trace preparation on every candidate repetition.

| Field degree / weight | Lifted points | Orbits | Primary | Fresh-process confirmation |
| ---: | ---: | ---: | ---: | ---: |
| 11 / 3 | 77 | 7 | 1.304x | 1.300x |
| 13 / 3 | 117 | 9 | 1.423x | 1.367x |
| 53 / 2 | 424 | 8 | 2.029x | 2.010x |
| 131 / 2 | 4,585 | 35 | 4.019x | 4.001x |

The first complete calls also improved in every cell (1.407–3.989x in
confirmation), with preparation included. The benchmark excludes shared
`NormalView` setup and later IC phases. It supports an opt-in factor-base
optimization, not an end-to-end DLP speedup.
