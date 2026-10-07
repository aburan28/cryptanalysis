# One-multiplication unit orbit plane

## Frozen hypothesis

The three x-coordinates of each prepared j=0 seed satisfy
`x + beta*x + beta²*x = 0`. The existing unit-coordinate plane obtains
both nontrivial coordinates with a Montgomery multiplication. Compute
`beta*x` with one multiplication, then derive `beta²*x` as
`-(x + beta*x)` with one field addition and one subtraction from zero.
Keep the full 1,392-byte plane layout, all digit recodings, rho policy,
batch normalization, and scalar verification unchanged. The expected
preparation count is 18 rotations for 18 nonidentity seeds rather than
36; evaluation rotations stay zero. Test every derived coordinate against
independent multiplication by `beta²`.

This is an arithmetic simplification of the opt-in plane format, not a
claim of a novel endomorphism. The primary question is a verified
one-target rho solve on the same frozen public point with the same
resource envelope. Report the exact target-dependent interval from the
first startup computation through scalar recovery and independent
verification, along with separate replay timing and exclusive operation
counts. Compare serial `reference,paired2-batch,paired2-plane-batch,
paired2-plane-batch,paired2-batch,reference` runs with fresh rho tables.

The first fixture in this directory exposed a stale expectation in the
full `test_curve` suite: it still asserted 36 preparation multiplications.
Retain that fixture and its panels as development evidence. Freeze the
corrected implementation, full unit tests, fixture generator, and checker
in a commit before deriving `fixture-v2.json` with the independent affine
Python oracle. Freeze the v2 fixture in a second commit before invoking
the solver. Preserve every raw success or failure and source/binary
hash. The old unit-plane point may be used only for development. CPU wall-time ratios
from this unisolated host remain exploratory; the AGENTS.md isolation
receipt is required for any controlled speedup claim or automatic routing.
