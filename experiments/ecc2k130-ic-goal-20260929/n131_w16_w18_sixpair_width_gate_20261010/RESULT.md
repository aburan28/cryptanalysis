# W16 cuts the six-pair prefix-support floor to 32

For the N131 same-rotation six-pair policy, widening the polynomial source
from W15 to W16 raises the exact signed tuple-support ceiling by about 992-fold
while doubling the projected factor base. The union-bound floor for a
target-independent signed first-pair prefix falls from **7,914 to 32** for
50% coverage of a uniform subgroup target. Under a 600-second one-worker
budget, those 32 prefixes leave at most **18.75 seconds each on average** for
the complete target-dependent prefix procedure. This is a necessary
arithmetic gate, not an observed relation rate.

The curve is `EC1N131Ckb1heb5f1998f20b` over
`GF(2)[t]/(t^131+t^13+t²+t+1)`, with
`r=680564733841876926932320129493409985129` and
`y²+xy=x³+1`. Wd is `span(t,…,t^d)`. Six signed pairs use Frobenius
rotations `0,13,26,39,52,65`; pair blocks 2–3 and 4–5 each share one
normalized mask-XOR seed. Within-pair folded-column collisions are excluded.

| Width | Rational masks | Actual projected B | Folded K | Signed pair states N | Same-seed two-pair states M | Tuple ceiling / uniform target | Minimum first-pair prefixes for half-union ceiling |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| W15 | 16,441 | 197,292 | 16,381 | 540,579,832 | 8,918,874,017,088 | 34,156.259 | 7,914 |
| W16 | 32,796 | 393,552 | 32,675 | 2,151,089,140 | 70,608,489,011,888 | 33,896,995.877 | 32 |
| W17 | 65,831 | 789,972 | 65,710 | 8,667,308,960 | 573,150,305,454,912 | 36,260,698,990.754 | 1 |
| W18 | 131,307 | 1,575,684 | 131,068 | 34,482,792,912 | 4,535,967,306,719,616 | 35,948,043,512,033.342 | 1 |

For each nonzero seed `s`, let `c_s` count signed, distinct-column pair
states. The [frozen count](result.json) uses `N=Σ_s c_s`,
`M=Σ_s c_s²`, and `N²M²` for the six-pair tuple ceiling. With one
target-independent first pair fixed, the remaining source ceiling is
`N M²`; hence the prefix floor is `ceil(r/(2 N M²))`. Cross-pair
column exclusions and exceptional intermediate group sums can only reduce
that support. The table's `B` counts distinct nonidentity subgroup-usable
points before sign/Frobenius folding; `K` is the separate effective column
count. `candidate_id` remains null because this census has no complete
relation and recovery pipeline.

The [source exporter](export_support.cpp) enumerated every W15–W18 mask in
Gray order and the [count](count.py) used an integer XOR transform plus
explicit same-column corrections. W15's support file is byte-identical to
the earlier W15 census and reproduces its signed-pair, same-seed, and
six-pair counts. The [independent native audit](audit_result.json) checked
491,516 mask/width rationality cases, every canonical Frobenius column, and
direct `x([4]P)` projection for all four widths. It recovered the exact B
values above. The [frozen protocols](protocol.json) and
[audit protocol](audit_protocol.json) bind sources, inputs, binaries, a
120-second cap, one worker, and 4 GiB; both receipts passed. Their wall
times are diagnostic on a host without an isolation receipt.

The immediate solver gate is the W16 exact signed-prefix five-pair residual
on the existing N131 constructed control, followed by an unpinned ordinary
target with all failed attempts charged. The first gate is recorded in the
[W16 five-pair result](../n131_w16_fivepair_sat_gate_20261010/RESULT.md).
