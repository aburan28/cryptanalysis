# 64 MiB budget-optimal tau cover

The radix-1024 secp256k1 fixed-generator multiplier has a tau-only cover
with **83,878 full-window seeds and 7,010 tau-squared classes**. This
attains the exact class-count lower bound for the declared 64 MiB retained
table format. The construction reties the exact-size cover to expose
11,634 adjacent triple pairs and applies 10,461 `3+3 -> 2+2+2`
replacements. The [proof](PROOF.md) gives the lower bound and construction.

The [independent cover check](check.json) verifies 174,764 classes and all
1,048,576 residues. The [native atlas check](native-atlas-check.json)
independently verifies the reindexed `DR20` table and inverse unit
transforms over the same residue space. The full atlas is 1,733,640 bytes.
The constructor projected 67,108,820 retained bytes. The native evaluator
reports **67,108,816 bytes**, leaving 48 bytes of the 64 MiB budget; the
four-byte difference comes from the aligned atlas representation.

The candidate source, cover, and verifiers were frozen at commit
`f18fd59c7779aa12cd34c89abac7ce14e1151cd8` before drawing the final
4,096-scalar panel. The [input receipt](holdout-inputs.json) binds the
scalar stream and checks modular disjointness from all listed earlier
panels, including the preflight panel below. The [path check](holdout-check.json)
reconstructs every scalar, checks each digit and terminal, and computes
128 independent binary points.

| Paired final panel | Previous phase-optimal | 64 MiB budget-optimal |
| --- | ---: | ---: |
| Full-window seeds | 73,417 | **83,878** |
| Tau-squared class assignments | 27,932 | **7,010** |
| Nonzero full-window terms | 49,152 | 49,152 |
| Tau-squared digits | 7,784 | **1,995** |
| Active tau-squared buckets | 3,595 | **1,794** |
| Grouped unit rotations | 18,223 | **16,102** |
| Occupied buckets | 11,781 | **9,984** |

The [phase receipt](phase-cost.json) reports the paired per-scalar
rotation-difference distribution. These are algorithmic operation counts.
The source-pinned native release replay passed all **4,096** cases against
the independent control and checked the first **128** against a separate
binary multiplication path. It reported 49,152 additions, 16,102 grouped
rotations, and the retained size above. The complete Rust suite is running.
The [raw targeted log](native-targeted.log.gz) and
[native receipt](native-targeted-check.json) bind the generated source,
atlas, inputs, certificate, executable and result.
CPU wall-time comparison requires the host-isolation and noise gate in
`../../docs/ISOLATED_BENCHMARKS.md`.

The first frozen panel is retained as a source-binding preflight. Its path
and independent checks passed, while `phase_cost.py` exposed a stale key
before phase counts could be produced. The corrected source is frozen
again before drawing the final panel, which excludes those preflight
scalars.
