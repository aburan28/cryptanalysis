# Cache-budgeted three-image Eisenstein cover

This design trades some of the minimum three-image atlas compression for
fewer exponent-two digits while retaining the twelve radix-1024 shift
windows, exact terminal residual, and three-bucket evaluator. It is a
new candidate because its full-window seed set and code assignment differ
from the minimum-memory three-image cover.

The immutable construction input is the full-residue tau-cycle order and
minimum-cardinality partition in
`experiments/prime-j0-power2-tau2-20261011/build_atlas.py`.
Scan cycles and their ordered segments deterministically. For each
nonoverlapping adjacent pair of length-three segments, replace the six
covered classes by three length-two segments. Select the first **4,096**
such pairs across the ordered cycles. No measured scalar or target affects
the selection. All length-two segments are admissible because every full
class has a minimum-norm digit satisfying `3N(d)<=1024^2`.

The resulting full atlas has 77,513 seeds and 19,807 exponent-two
classes. The unchanged terminal atlas has 9,288 seeds. Twelve full rows
and one terminal row contain 939,444 affine slots. With the same native
table representation, retained bytes are predicted to be 64,991,220,
which leaves 2,117,644 bytes below a reported 64 MiB cache capacity.
This byte figure is an exact layout projection until a native table is
built and its `size_of` accounting is checked. Cache residency and CPU
timing require a host-isolated paired measurement.

Freeze the deterministic plan, proof, independent verifier, binary
digest, and input law before drawing a new full-range scalar panel
disjoint from the prior panels. Verify every full residue and terminal
pair, then compare scalar reconstruction, point results, mixed additions,
outer tau calls, grouped rotations, native retained bytes, and complete
operation boundaries against the minimum-memory three-image format on
that same panel. A lower exponent-two class count is a construction
property, not a measured runtime gain.
