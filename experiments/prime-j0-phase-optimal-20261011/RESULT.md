# Exact phase-optimal tau cover at minimum memory

The radix-1024 fixed-generator secp256k1 multiplier has a **73,417-seed
tau-only cover with exactly 27,932 forced tau-squared classes**, the
lexicographic minimum for `(seed count, tau-squared class count)` under
the declared `N(digit) <= 1024^2` format. The previous exact-size
cover has 31,165 tau-squared classes. The new cycle plan removes
**3,233** such assignments without adding a table row.

The [proof](PROOF.md) describes the cyclic Boolean-state optimum. The
[constructor](construct.py) selects eligible segments and the
[independent verifier](verify.py) checks a separate Boolean DP, every
class assignment, and all **1,048,576** residues. The [cover receipt](check.json)
binds the serialized `LP21` cover. The [native atlas verifier](native-atlas-check.json)
checks all residues again after reindexing into the `DR20` layout. The
native atlas is **1,691,796 bytes**, with **890,292** precomputed affine
slots including the terminal table, matching the preceding exact-size
cover's layout and memory requirement.

The candidate source, cover and verifiers were frozen at commit
`dfe1e80` before drawing a new 4,096-scalar panel. The
[input receipt](holdout-inputs.json) binds the scalar stream and checks
modular disjointness from 43 listed earlier panels. The
[path verifier](holdout-check.json) reconstructs every scalar from its
digits, checks the group map and terminal, and computes 128 independent
binary point fixtures.

| Paired fresh panel | Previous exact-size cover | Phase-optimal cover |
| --- | ---: | ---: |
| Full-window seeds | 73,417 | **73,417** |
| Tau-squared class assignments | 31,165 | **27,932** |
| Nonzero full-window terms | 49,152 | 49,152 |
| Tau-squared digits | 8,782 | **7,799** |
| Active tau-squared buckets | 3,723 | **3,589** |
| Grouped unit rotations | 18,371 | **18,077** |
| Occupied buckets | 11,903 | **11,769** |

The [phase receipt](phase-cost.json) counts the grouped buckets from
the frozen paths. This is an exact algorithmic path comparison; native
point replay is in progress. CPU wall-time comparison requires the
host-isolation and noise gates in
`../../docs/ISOLATED_BENCHMARKS.md`.
