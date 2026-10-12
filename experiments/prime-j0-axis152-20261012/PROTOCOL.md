# Sixteen-window radix-152 axis format

For a public scalar on secp256k1, use the pinned nearest Eisenstein
representative from the repository's certified GLV reducer. Apply sixteen
nearest four-corner radix-152 digit steps. Each ordinary table stores one
affine point per six-unit residue orbit at its positional weight. Rotate
the terminal pair into the unique sector `(-u,b)` with `u <= 3b < 2u` and
use two one-dimensional point tables for `(-u,0)` and `(0,b)`.

The universal terminal bound is `3Q(t) <= 17,574,891`, where
`Q(a,b)=a^2+3ab+3b^2`; it gives `1 <= u <= 4,840` and
`1 <= b <= 3,226` for a nonzero terminal. The ordinary atlas has 3,852
orbits per window. The exact bound-based table therefore has 69,698
affine point entries, with a 4,460,672-byte payload at 64 bytes per point.
This is the minimum over integer radices at least two for the specified
sixteen-window, two-axis construction.

`search.py` independently counts all radix-152 residues and checks the
global integer-radix census. `screen.py` reconstructs the existing frozen
4,096-scalar design panel and compares selected-term counts with the
radix-416 design on the identical representatives. `check.py` builds the
central Lean theorems and audits their axioms. These sources and outputs
are frozen before generating a disjoint public-point holdout. Freeze the
holdout generator and independent replay implementation before drawing
its scalar inputs. A native evaluator must then rebuild the point tables,
audit the atlas, and replay every held-out public point.

For a CPU speed comparison, pair complete multiplications on the same
frozen scalars and resource envelope under the repository's isolated
benchmark preflight. Preserve the raw run order, failures, operation
counts, retained bytes, and independent point checks.
