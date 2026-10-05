# Unit-folded orbit graph for public scalar multiplication

This experiment changes how the complete tapered residue-orbit point table
from PR #287 is built. It does not change the table contents, block schedules,
scalar recode, or online lookup. Every nonzero correction has a τ-NAF digit
stream of depth at most three. Remove its highest nonzero digit. The remaining
exact coefficient is a unit transform of another correction in the same
width's complete orbit table, and that parent has depth one less. Thus every
correction point can be constructed by transforming a previously built
projective point and adding one shifted digit point. A deterministic graph
recipe holds the parent orbit ID and unit, the digit slot and position, and
the depth. Process depths one through three, then batch-normalize once per
block. The graph must verify exact coefficient identities for **every** orbit
before C source generation.

The predecessor screen is exhaustive for widths 8, 10, and 12. There are
1,095, 9,843, and 88,575 orbits, respectively. The direct builder requires
1,044, 15,606, and 168,192 mixed additions per block; graph construction
would require 1,044, 9,774, and 88,488. Under the frozen schedules, the
projection is 39,096 instead of 62,424 setup additions on the smaller
subgroup and 267,552 instead of 506,664 on the larger. The graph uses extra
unit rotations and static recipe bytes, which must be measured. These are
exact operation projections, not CPU timing results.

## Prospective gate

Commit this protocol and the exhaustive recipe generator, then open a draft
PR before generating any new evaluation scalars. Compare direct versus graph
construction on the same two curves and public points, using the existing
`tapered-inputs.json` only as a frozen correctness regression. For an
independent prospective preparation panel, use generator and `37P` on each
curve plus two further public points fixed as `101P` and `103P` before native
evaluation. The primary comparison is preparation operations and memory;
online outputs and operations must be identical to the direct builder on all
16,384 previously frozen scalar inputs. The graph gate requires every output
to match its generic digest, all preparation additions and rotations to
match an independent Python recipe model, exactly one point-table
normalization per nonzero block plus the positional base normalization, no
extra point-table bytes, and correct raw failure retention. Do not claim a
setup wall-time win without a physical host that passes
`docs/ISOLATED_BENCHMARKS.md`. Local timing remains exploratory. This format
is variable-time and restricted to public research scalars.
