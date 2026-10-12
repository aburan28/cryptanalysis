# Point-only U14 table with computed unit-orbit digits

Mode 129 keeps the four-limb affine point windows and the grouped
Jacobian gauge of modes 127 and 128. It computes the canonical orbit
representative, orbit rank, unit action, and nearest lattice digit
during recoding. Only the affine point windows are retained after table
preparation. Mode 128's canonical digit array is its paired reference.

For residue `(a,b)` modulo `m=2^w`, `w in {9,10}`, compute the three
rotation images under `omega(a,b)=(a+3b,-a-2b)`, and their negatives,
using a power-of-two bit mask. Choose the lexicographically smallest
image and the least inverse action code on ties. Rank this canonical
pair by the three-interval formula in the mode 128 proof. Compute its
digit with the existing four-corner nearest-lift rule, then apply the
chosen unit action. At table construction, use temporary canonical
digits to build the identical affine windows and release those digits
before online evaluation.

Commit this protocol and the implementation before generating the new
4,096-scalar panel from seed `20261010129`. Require new reduced scalars
to be unique and disjoint from all earlier U14 panels. Exhaustively
compare every radix-512 and radix-1024 residue against mode 128's
digit, orbit rank, and unit code. Compare all independently constructed
affine table entries, all 129 frozen fixture points in each mode, all
4,096 new scalar points and fourteen choices, and the first 128 new
points against independent binary scalar multiplication. Retain
preparation, process RSS, full-suite results, failures, and hashes of
source, inputs, binary, and raw outputs.

The primary timing question is the complete single-scalar online
interval on the same public point: representative selection, recoding,
orbit/digit computation, lookup, gauge/addition work, inversion,
formatting, and expected-point verification. Keep table construction
outside that interval. Pair modes 128 and 129 on an isolated Linux host
with the repository benchmark service; preserve failed preflights and
noise-gate results. Contended local timings are diagnostic.
