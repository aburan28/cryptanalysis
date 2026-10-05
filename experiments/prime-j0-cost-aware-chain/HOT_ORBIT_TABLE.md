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

## Executed gate after protocol freeze

The protocol and selection list landed in commit `0d7e6171` and draft PR
#274 before any candidate evaluation fixture was generated. The new fixture
uses seed `20261211`, the same four public curve/point cases as the earlier
panels, and separate scalar streams with exact uniform sampling by
rejection. `make_hot_inputs.py` froze the scalar files and generic-multiplier
output digests before the hot candidate was compared. The generated hot map
binds the exact 2,048 selected orbit IDs.

`check_hot_panel.py` paired `pos-batch128`, `fused-orbit-batch128`, and
`fused-hot-batch128` on all four inputs. Every one of the 16,384 hot outputs
matched the frozen generic digest and passed scalar replay. The table reports
executed counts; the retained saving is
`(pos_adds - hot_adds) / (pos_adds - full_orbit_adds)`:

| Frozen case | Positional adds | Full orbit adds | Hot adds | Retained saving | Full → hot setup adds | Full → hot total prep bytes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 32-bit subgroup, generator | 15,637 | 8,336 | 9,164 | 88.66% | 19,440 → 8,192 | 669,424 → 300,144 |
| 32-bit subgroup, `37P` | 15,630 | 8,322 | 9,176 | 88.31% | 19,440 → 8,192 | 669,424 → 300,144 |
| 56-bit subgroup, generator | 33,501 | 19,400 | 23,524 | 70.75% | 29,160 → 12,288 | 985,136 → 431,216 |
| 56-bit subgroup, `37P` | 33,521 | 19,451 | 23,533 | 70.99% | 29,160 → 12,288 | 985,136 → 431,216 |

All four cases pass the preregistered gate of retaining at least half of the
full folded table's saved additions. `hot-panel.json` retains raw outputs,
operation counts, failures, timings, and source hashes. Its `fallbacks` field
counts cold eight-digit blocks in the hot mode, including one-digit and zero
blocks that need no extra addition, plus any out-of-span scalar fallbacks.
The full folded mode retains its original scalar-fallback meaning. No panel
case had an out-of-span fallback in the full folded arm.

The local CPU timings remain exploratory because this host lacks the required
isolation receipt. Only a qualifying isolated host and paired one-target rho
accounting can support a wall-time claim. Charge this fixed-point table's
setup when a target or base point makes it target-dependent. Academic novelty
remains unestablished.
