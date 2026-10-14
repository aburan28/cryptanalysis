# Radix-569 bounded top-ball scalar format: frozen protocol

Represent a secp256k1 scalar by the nearest Eisenstein-lattice pair
`z = a + bτ`, with `τ² - 3τ + 3 = 0` and `a + bλ ≡ k (mod n)`.
Use thirteen radix-569 four-corner nearest-digit steps and one bounded
terminal lookup. Each ordinary table and the terminal table store one
affine point per six-unit orbit. The existing Pareto gauge tree combines
the selected points. This format uses fourteen selected terms for the
ordinary scalar case.

The universal residual bound is `3Q(top) ≤ 270666`, where
`Q(a,b) = a² + 3ab + 3b²`. The bounded set has 327,235 integer pairs in
54,540 unit orbits. Its canonical sector uses a 601-element row-prefix
array. Each ordinary table has 53,961 unit orbits; the full format has
756,033 affine point entries and 48,386,112 point bytes at 64 per entry.

`radix_search.py` computes the exact bound-based entry count for every
integer radix from 500 through 700, including even and 3-divisible bases,
using the six-unit Burnside count. Radix 569 minimizes this stated census.
`topball.py` exhaustively verifies the final bounded set and its row rank.
`screen.py` audits all 323,761 residues and replays the previously frozen
4,096-scalar design panel from
`experiments/prime-j0-sector-digit-20261010/fresh-inputs.json`.
It compares source operation counts with radix 943 on the same scalars.
The existing radix-671 split-top design rows supply a second paired
14-term comparison.

The design source, proof, and receipts are frozen before a new holdout is
drawn. The holdout generator uses `random.Random(20261012569)` and draws
512 distinct scalars as `getrandbits(256) % n`. Its independent Jacobian
double-and-add implementation supplies the expected public points.
The replay reconstructs the scalar from all selected digits, accumulates
each selected point with a separately implemented affine group law, and
checks every expected point. Preserve per-case rows, failures, and source
hashes.

The point entry and operation counts are exact for the declared format and
source model. Complete retained memory and CPU timing require a native
implementation. A paired CPU comparison must use a qualifying isolated
host receipt and identical inputs, resource limits, and online boundaries.
