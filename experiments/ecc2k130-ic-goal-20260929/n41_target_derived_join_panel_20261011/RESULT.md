# Seed-conditioned product images reject target-derived relaxed joins

A frozen, same-public-target N41 panel produced **nine relaxed two-pair hits among 512 controls and zero exact transported-pair hits**. The known positive hit both constructions. Independent Sage replay verified all 512 control derivations from the same raw public preimage, every relaxed hit, and the exact-domain classification of all ten relaxed hits. Each of the nine relaxed-only hits fails the seed-conditioned product-image test on its right pair; seven also fail it on the left. This identifies a specific algebraic constraint to carry into a target-conditioned N131 solver.

## Exact product-image gate

Write the source mask coordinates in `W_d=span(1,t,...,t^(d-1))`, factoring out the common `t` used by the actual source space `tW_d`. Fix a nonzero mask seed sum `s=a+b`. The corresponding product mask is

`p=ab=a(a+s)=a²+sa`.

For fixed `s`, `L_s:a↦a²+sa` is linear over `GF(2)`. Its kernel is exactly `{0,s}`: the field has no zero divisors, so `a(a+s)=0` implies `a=0` or `a=s`. Thus its image has dimension `d-1`. The unrestricted low-power product span has dimension `2d-1`, so the exact product image occupies a fraction `2^(-d)` of that span before rationality and column checks. This is **1/64 for W6** and **1/32,768 for W15**. The [complete rank census and witness audit](factorization_gate.json) confirms rank 5 for all 63 W6 seeds and rank 14 for all 32,767 W15 seeds. Its source independently checks image membership against explicit W6 atom roots for every relaxed hit.

An adaptive parity-check basis for each W15 seed needs 15 checks on 29 product coordinates. Storing all 32,767 matrices densely bit-packed takes `32,767 × 15 × 29 = 14,253,645` bits (about 1.70 MiB), apart from indexing and alignment. The table is a small reusable mathematical object; selecting its checks for an unknown seed inside a target-conditioned search remains the implementation problem. A fixed choice of the 14 odd product coordinates is insufficient: the [rank census](factorization_gate.json) finds odd-coordinate rank 14 for 12,288 of 32,767 seeds, with lower ranks for the rest.

## Frozen public-target-derived panel

The checked Sage [producer](make_panel_sage.py) held the same raw public preimage `U` and one verified first-half pair point `B` fixed. It varied a second exact first-half pair `A` with distinct factor-base columns and formed each required right-middle point `V=U-A-B`. After requiring nonzero, trace-zero reciprocal `1/x(V)` and distinct `V`, 1,711 eligible points remained. A frozen `Random(20261011)` shuffle selected 512 without reference to the subsequent right-side outcomes. The [protocol](protocol.json) binds the inputs, native sources and binaries, compiler, resource limits, and predecessor receipts.

| Complete one-worker component panel | Relaxed pair domain | Exact transported W6 pair domain |
| --- | ---: | ---: |
| Distinct points per right-side pair rotation | 128,656 | 1,956 |
| Known positive middle point | hit | hit |
| 512 target-derived controls | 9 hits, 503 exhausted misses | 0 hits, 512 exhausted misses |
| Reusable setup | 0.851096 s | 0.007981 s |
| Sum of 513 target-dependent query intervals | 189.766321 s | 1.034431 s |
| Peak process RSS | 30,392,320 B | 2,670,592 B |

Both runs completed every query under their frozen 600-second panel and 4-GiB limits. The relaxed [receipt](relaxed_receipt.json) includes each group probe and returned pair witness; the exact [receipt](exact_receipt.json) records all 1,956 pair probes per query, group hits, and cross-pair column checks. The [Sage replay](sage_replay.json) independently rebuilt both exact pair domains and checked all ten relaxed hits: one exact hit and nine exact misses. The [paired audit](audit.json) binds the source and result hashes and preserves the 513 matched rows. Setup is reusable and outside each target-dependent query interval. These local CPU times are exploratory on an unisolated host; the comparison demonstrates exact domain and outcome differences, not a controlled wall-time speedup against rho.

The observed control rate is 9/512 for the relaxation and 0/512 for exact pairs under this restricted first-half law. If the seeded shuffle is modeled as uniform sampling without replacement from the 1,711 eligible points, exact hypergeometric inversion gives a central 95% interval of **17–52 relaxed hits** in that eligible pool and a one-sided 95% upper bound of **8 exact hits**. These are design-based uncertainty calculations for this pool and input law, not estimates for arbitrary curve targets or N131 relation yield.

## N131 transfer gate

The W15 public-query source has 540,579,832 signed pair states per rotation, so a full exact pair table is outside the intended 4-GiB path. The next implementation should attach the 15 seed-conditioned product-image checks to target-conditioned pair witnesses before materializing pair outputs, then test whether they reject whole coefficient families in an unpinned N41 query. An N131 attempt should follow only with a source-bound work and memory projection under the one-worker, 600-second, 4-GiB gate. This remains a component design (`candidate_id: null`).
