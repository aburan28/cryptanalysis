# Budgeted hot-orbit table: prospective format

The full eight-digit table prepares 29,593 point entries per block. Folding
the six curve units reduces that to 4,933 entries. A further option is to
prepare only the 2,048 two-digit orbits that a fixed scalar law uses most
often. A lookup hit uses one mixed addition after unit reconstruction. A
lookup miss reconstructs the two four-digit points from the existing
positional table and uses at most two mixed additions. Zero and one-digit
blocks need no fused table entry. The fallback is exact for every scalar;
the frequency model affects work, never the answer.

This combines the four-step residue atlas, eight-digit pair fusion, six-unit
orbit quotient, a bounded frequency table, and positional fallback. The
budget makes setup and table memory predictable. It may be useful when a
full folded table is too expensive to build or retain for a fixed public
point. It is variable-time research code; no private-scalar use is proposed.

## Frozen selection rule

`screen_hot_orbits.py` fixes a 2,048-entry budget. For each subgroup order
23,729,779 and 53,624,256,071,278,747, it includes both order-three
Eisenstein eigenvalues. For law index `i` in that order, 5,000 uniform
subgroup scalars come from SplitMix64 with initial state `20261101 + i` and
rejection sampling for exact uniformity. Each scalar uses
the shortest L1 lattice representative selected by the existing baseline
reducer. The script counts only eight-digit blocks with two nonzero atlas
patterns, pools the four laws, and ranks orbit IDs by descending frequency
with smaller ID breaking ties. The selected list and its SHA-256 are in
`hot-orbit-screen.json`. This is a fixed selection policy for the proposed
implementation; point coordinates do not enter the ranking.

The script separately screened 5,000 scalars per law from SplitMix64 state
`20261201 + i`. Those results helped choose the budget and
are **exploratory**, not an acceptance holdout:

| Subgroup order | Eigenvalue index | Two-digit hot coverage | Full folded setup adds → proposed hot setup adds | Incremental affine table, full → proposed hot |
| --- | ---: | ---: | ---: | ---: |
| 23,729,779 | 0 | 88.83% | 19,440 → 8,192 | 631,424 → 262,144 B |
| 23,729,779 | 1 | 88.86% | 19,440 → 8,192 | 631,424 → 262,144 B |
| 53,624,256,071,278,747 | 0 | 83.65% | 29,160 → 12,288 | 947,136 → 393,216 B |
| 53,624,256,071,278,747 | 1 | 71.33% | 29,160 → 12,288 | 947,136 → 393,216 B |

Coverage is the fraction of **two-digit orbit uses** that hit the selected
table. It is not the fraction of scalars solved, an executed addition count,
or a wall-time speedup. Setup additions and incremental affine bytes are
cardinality predictions: 2,048 two-digit entries per block versus 4,860
two-digit additions among 4,933 full folded entries. Both formats also need
the same positional base and its preparation. The 32-byte point size is the
current `ca_elem` layout and must be checked on the target build.

## Next experimental gate

Commit this protocol before generating any candidate evaluation fixture.
Then implement a compact orbit-ID-to-hot-index map and the exact positional
miss path. Generate four new 4,096-scalar curve/point cases with seed
`20261211`, using the same public points as the fused and orbit panels but
new scalar streams. Freeze scalar files and independent generic-multiplier
digests before running the candidate. Pair `fused-orbit-batch128`, the hot
candidate, and `pos-batch128` on each input. Preserve operation counts,
setup counts, table bytes, misses, failures, and raw timings. Require every
output to match independent generic multiplication and require at least half
of the full folded table's saved online additions to remain in each case.

The operation gate is a reason to continue testing, not a speedup claim.
Only an isolated host receipt and paired one-target rho accounting can
support a CPU wall-time claim. Charge this fixed-point table's setup when a
rho target or base point makes it target-dependent. Academic novelty also
remains unestablished.
