# Fourteen-window mixed-radix tau atlas

This candidate uses six radix-512 and eight radix-640 windows with the
existing two-bucket tau identity and grouped-unit gauge. The exact
[coverage and termination proof](PROOF.md) gives **415,190 affine seed
points**, a 26,572,160-byte point payload, and 4,729,980 bytes of binary
atlases. The new full and final radix-640 atlases decode all 409,600
residues and satisfy their declared norm bounds.

The independent affine design replay checked 64 scalars from the prior
frozen panel. Both per-term and grouped-gauge evaluations agreed with
binary scalar multiplication and exact Eisenstein reconstruction. It
recorded 832 mixed additions and 228 gauge rotations. A disjoint panel
will be generated after this source is frozen.

The shared native evaluator source is reserved by an earlier Conductor
task. Native operation accounting and controlled CPU timing are subsequent
gates. The current RunPod Pod does not pass the host-level isolation
preflight in [the benchmark protocol](../../docs/ISOLATED_BENCHMARKS.md).
