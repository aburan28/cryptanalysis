# Ordinary N53 weight-five balanced-S3 screen

Q20261010191500 raised all four normal-x leaf bounds from weight four to
five while preserving the exact ordinary public point, raw-preimage coset,
balanced S3 chain, CryptoMiniSat binary, and one-thread seed-zero settings
of Q20261010183500. The builder first reproduced the archived weight-four
formula byte for byte. The new formula has **27,338 variables, 100,884 CNF
clauses, 795 native XOR rows, and 25,281 shared AND gates**. The input is
`EC1N53Ckb1hf77aab617904`, workload `W74f2979b3e68`, and
`isogeny: "none"`.

| Ordinary cell on the same public point | Conflict cap reached | Status | Child CPU | Wall | Verified relations under cap |
| --- | ---: | --- | ---: | ---: | ---: |
| Weight≤4, Q20261010183500 | 1,000,001 | `BOUNDED_UNKNOWN` | 134.59 s | 323.78 s | 0 |
| Weight≤5, Q20261010191500 short cell | 100,001 | `BOUNDED_UNKNOWN` | 14.95 s | 16.66 s | 0 |
| Weight≤5, Q20261010191700 matched cell | 1,000,001 | `BOUNDED_UNKNOWN` | 119.89 s | 161.74 s | 0 |

Both weight-five stream and receipt audits passed. The weight-five bound
has not been enumerated into an exact projected factor base, so its actual
`B`, folded `K`, and any IC candidate ID remain null. Its formula and
ordinary-query statuses are valid stage observations. All CPU/wall figures
come from a shared host and do not establish a speedup; the capped searches
provide neither a natural relation rate nor rank novelty.

The million-conflict comparison tests a larger leaf bound under matched
solver settings. It still does not measure the work for a successful
decomposition: both runs were censored at the same conflict limit. The
next solver improvement should change the search mechanism rather than only
loosening leaf weights, and should first return verified ordinary relations
at N53 and N83. Enumeration of multiple distinct solutions per successful
query, followed by incremental rank accounting, is particularly relevant
to the N131 weight-seven frontier in Q20261010190000: its large mean
representation count helps relation collection only if useful models can
be found and extracted at an affordable cost. The complete-solve `2^x`
remains unknown pending those rates, matrix costs, and common operation
calibration.
