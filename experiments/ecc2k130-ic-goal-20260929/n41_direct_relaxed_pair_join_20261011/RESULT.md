# Exact N41 two-pair group join

An exact enumeration of the rotated W6 pair relaxation produced 128,656 distinct curve points. A group meet in the middle found a verified sum for the frozen positive middle point and exhausted the complete relaxed pair space for each of eight target-derived middle points. Independent Sage replay checked the positive witnesses, Frobenius rotations, and group sum.

## Method

The field is `GF(2)[t]/(t^41+t^3+1)` and the curve is `y²+xy=x³+1`; its order is `2,199,025,563,772`, with odd subgroup order `549,756,390,943`. The candidate remains a component design (`candidate_id: null`). The frozen [protocol](protocol.json) binds the source, helper, binary, nine input points, compiler, host, and caps.

For each nonzero six-bit seed sum `s` and eleven-bit product coefficient `p`, enumerate solutions of the linearized reciprocal equation

`p z + H((s+z)²) + ε = 0`, with `ε ∈ {0,1}`,

where encoded `s` and `p` occupy the source W6 seed and product spans. Retain nonzero trace-zero `z` for which `x=1/z` lifts to a curve point, with both curve signs. Frobenius rotations 20 and 30 yield the left and right point sets. For each fixed middle point `M`, probe `M-L` in the right hash table for every left point `L`, stopping at a hit or complete exhaustion. This is a superset of genuine W6 pairs because the seed sum and product were not required to share individual source atoms.

## Measured component result

| Quantity | Recorded value |
| --- | ---: |
| Linear-map ranks 39 / 40 / 41 over 2,048 products | 255 / 1,269 / 524 |
| Raw reciprocal solutions | 257,310 |
| Nonzero trace-zero solutions | 128,385 |
| Curve-rational reciprocals | 64,347 |
| Distinct curve points after sign closure | 128,656 |
| Reusable setup | 514.778291 ms |
| Peak process RSS | 30,244,864 bytes |
| Frozen positive: status / probes / query | `RELAXED_SUM_HIT` / 21,713 / 11.465750 ms |
| Eight target-derived controls: status | `COMPLETE_RELAXED_NO_SUM` each |
| Each exhausted control: probes | 128,656 |
| Eight control query times | 56.517375, 56.618875, 43.953083, 46.259917, 42.601250, 56.978458, 69.898291, 98.190125 ms |
| Nine query time sum | 482.483124 ms |

The [native receipt](receipt.json) records all point coordinates, witnesses, per-query time, exact replay time, and caps. The [Sage replay](sage_replay.json) verifies the positive pair equation twice, both rotated coordinates, the curve equation, and the group sum; it also checks the frozen input mapping and full probe count on every exhausted query. An [exact source-coefficient check](source_pair_check.json) resolves the returned left and right witnesses uniquely to W6 atom pairs `(53, 59)` and `(1, 6)`, matching the positive input fixture. Each query time includes its group probes and internal exact relation check; the check time is a nested measurement, not an added phase. Setup is reusable and outside target-dependent query time. These CPU timings are exploratory because this host has no isolation receipt; they are not paired against rho.

The complete relaxed lists contain roughly `128656² / 2199025563772 = 0.00753` expected sums for a uniformly distributed full-curve point under an independent-set heuristic. The eight misses therefore measure exact membership for these fixed controls, not an unusually strong statistical rejection rate. The next design step is to express the same reciprocal and group-sum compatibility as a compact target-conditioned constraint, then test whether it avoids materializing the pair lists as the product span grows at N131. Preserve the positive witness and exhausted controls as regression gates for that encoding.

## Replay

From the repository root, compile the source with the command in the frozen protocol, then run `direct_join_native targets.txt receipt.json` with paths resolved under this directory. The `./sage --runtime-info` receipt was saved before the independent Sage check. Run the verifier through `./sage -python experiments/ecc2k130-ic-goal-20260929/n41_direct_relaxed_pair_join_20261011/verify_sage.py`.
