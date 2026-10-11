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
rotation-difference distribution. The mean change is **-0.518 grouped unit
rotations per scalar** (normal 95% confidence interval [-0.548, -0.488]);
2,041 cases improve, 1,522 tie, and 533 regress. Tau-squared digit use
falls by a mean **1.413 per scalar** (normal 95% confidence interval
[-1.451, -1.376]); 3,119 cases improve, 865 tie, and 112 regress. These
are paired algorithmic operation counts, not CPU timing ratios.
The source-pinned native release replay passed all **4,096** cases against
the independent control and checked the first **128** against a separate
binary multiplication path. It reported 49,152 additions, 16,102 grouped
rotations, and the retained size above.
The [raw targeted log](native-targeted.log.gz) and
[native receipt](native-targeted-check.json) bind the generated source,
atlas, inputs, certificate, executable and result.
The [native suite coverage check](native-suite-coverage.json) verifies all
**143** Rust tests against the same executable and generated assets. Its
coverage partition is 101 tests passed in the initial full-suite attempt,
the interrupted hybrid test passed alone, and two disjoint complementary
shards passed 21 and 20 tests. The initial attempt exited 101 without a
final Rust summary after the 101 passes; its
[raw log](native-full-attempt1.log.gz) and
[receipt](native-full-attempt1-check.json) preserve that outcome. The
[hybrid receipt](native-hybrid-isolate-check.json) and both
[shard receipts](native-shard-0-check.json) bind their exact test names,
raw logs, binary hash, and exit codes. The
[aggregate verifier](verify_native_suite_coverage.py) compares their
disjoint union with the executable's own 143-test listing.
CPU wall-time comparison requires the host-isolation and noise gate in
`../../docs/ISOLATED_BENCHMARKS.md`.

The first frozen panel is retained as a source-binding preflight. Its path
and independent checks passed, while `phase_cost.py` exposed a stale key
before phase counts could be produced. The corrected source is frozen
again before drawing the final panel, which excludes those preflight
scalars.
