# Fifteen-window grouped-unit tau buckets

Mode 157 groups the selected points of each tau bucket by six-unit power
and rotates each accumulated bucket at most twice. It keeps the fifteen
window schedule, 233,423 affine seed points, and 17,511,596 charged bytes
of mode 156. The exact group identity is in [PROOF.md](PROOF.md).

The first native test matched mode 156 on 4,096 earlier scalars, checked
the first 128 independently by binary multiplication, and counted 15,323
gauge rotations against 40,981 per-term rotations. The source and input
law are frozen before a new disjoint panel. Complete point replay,
source-level field-operation counts, and a Linux correctness replay are
the next validation gates. Controlled CPU wall timing requires the
[isolated host receipt](../../docs/ISOLATED_BENCHMARKS.md).
