# Radix-929 bounded top-state scalar format: frozen protocol

## Contribution and construction

Represent a secp256k1 scalar by the nearest Eisenstein-lattice representative
`z = a + bτ`, where `τ` satisfies `τ² - 3τ + 3 = 0` and
`a + bλ ≡ k (mod n)`.
Apply twelve radix-929 four-corner nearest-digit steps. Store each ordinary
digit in a unit-orbit table and store the remaining pair directly in a
bounded top-state table. Every entry is a point on secp256k1, and the six
unit images use the existing endomorphism and sign path. The top lookup is
ranked by a 953-element row-prefix array, without a top-state hash map.

The admissible top states satisfy `3(a² + 3ab + 3b²) ≤ 679762` for every
integer scalar when the initial nearest-representative and digit assumptions
in `DigitCover.lean` hold. The exact bounded set has 821,953 pairs in
136,993 unit orbits. Twelve ordinary tables contain 143,841 entries each;
the complete format has 1,863,085 point entries. At 64 bytes per affine
point, this is 119,237,440 point bytes. Auxiliary residue and prefix arrays
are reported separately.

## Source and independent panels

The design panel is the previously frozen 4,096-scalar file
`experiments/prime-j0-sector-digit-20261010/fresh-inputs.json`. The paired
reference is thirteen radix-943 unit-orbit windows on the same representative
and source operation model. `screen.py` saves one row per scalar and records
the input, source, plan-table and row digests. `topball.py` exhaustively
enumerates the bounded top states, checks each six-element orbit, verifies
the row-rank formula and records table digests. `check.py` builds the pinned
Lean modules and audits their axioms.

Freeze this design protocol, source and receipts in a commit before making
the holdout. Then generate 512 fresh scalars with Python `random.Random`
seed `20261012929`, using `getrandbits(256) % n`, and save the point expected
from an independent Jacobian double-and-add implementation. Replay the
radix-929 scalar decomposition and each point term using separate group-law
code against all 512 expected public points. Preserve every case row and
source hash. The holdout is a correctness check and source-operation check.

## Evidence boundary

Point-table size and modeled products are exact counts for this format and
the frozen source model. CPU timing requires the repository's isolated-host
receipt with exclusive CPU, NUMA, frequency, interrupt, quota, and noise
gates. The current Runpod container does not establish those host controls.
Native integration must wait for the separate writer holding the source
files, then use a correctly isolated benchmark host.
