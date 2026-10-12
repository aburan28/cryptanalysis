# Axis-factorized radix-416 design result

Thirteen radix-416 unit-orbit windows and two terminal axis tables cover
the complete secp256k1 scalar range with **433,578 affine point entries**,
or **27,748,992 point payload bytes** at 64 bytes each. The exact
bound-based search proves radix 416 is the unique point-entry minimum
among integer radices at least two for this thirteen-window two-axis
construction. Lean checks the universal digit and terminal bounds,
scalar reconstruction, sector selection, and axis factorization.

| Frozen design measure | Radix 569 top-ball | Radix 416 two-axis |
| --- | ---: | ---: |
| Scalar cases | 4,096 | 4,096 |
| Affine point entries | 756,033 | **433,578** |
| Point payload at 64 bytes each | 48,386,112 | **27,748,992** |
| Selected terms | 57,344 | 61,440 |
| Ordinary residues audited | 323,761 | 173,056 |

The new format removes **322,455 stored point entries**, or
**20,637,120 point payload bytes**, relative to radix 569 and adds one
selected point term per scalar on this panel. Its exact ordinary table
count is `13×28,844=374,972`; the two axis tables contain 35,164 and
23,442 points. The complete retained native footprint and complete
operation cost remain to be measured after native implementation.

The design and Lean sources were frozen in commit `bbda8011a`. The
independent replay source was frozen in `b5dcf48f3` before drawing the
replacement seed-20261012417 holdout. That panel is disjoint from the
4,096 design scalars, the listed prior holdouts, and the retained
unqualified seed-20261012416 draw.

| Disjoint holdout measure | Radix 569 top-ball | Radix 416 two-axis |
| --- | ---: | ---: |
| Scalar and public-point cases | 512 | 512 |
| Selected terms | 7,168 | 7,680 |
| Independently verified final points | — | **512 / 512** |

The point-stream SHA-256 is
`0c1273d82e3f810444bd004a0fe16115d620115cb2f2538f85b6a6c46dd6ac82`.
Each terminal pair is separately reconstructed from two unit-rotated
axis terms, and an independent affine group law sums all selected points
against the fixture's public point. The [proof map](PROOF.md),
[search receipt](search.json), [design receipt](design.json), and
[holdout receipt](holdout-replay.json) retain the bounds, exact census,
source/input hashes, residue audit, and per-case checks. Native replay,
complete retained memory, and isolated-host timing remain the next gates.
