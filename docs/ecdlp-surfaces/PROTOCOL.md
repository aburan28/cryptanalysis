# Elliptic-curve surface tooling integration protocol — 2026-10-11

The requested deliverable is native Rust tooling in both `aburan28/crypto` and
`aburan28/cryptanalysis` to explore surfaces containing a genus-one curve and
check what preserves its group law for an ECDLP transfer. This integration
retains the existing small-field implementation and its public fixtures.

The bounded hypothesis is that the quartic embedding and its inverse preserve
the cyclic subgroup, and that the quadric-pencil classification and necessary
Frobenius-factor filter reproduce the committed results. It is a correctness
check, with no timing, speedup, or production-curve experiment.

Frozen inputs: prime 101, coefficients `a=1`, `b=46`, subgroup order 109,
`P=(2,37)`, public known-answer `Q=(64,19)`, and witness 37. The compatible
surface polynomial has coefficients `[14,251,1414,10201]`; the incompatible
control has `[0,202,0,10201]`. The tests also retain exceptional-point and
rank-two torsion rejection cases.

Acceptance requires release tests, formatting, warning-free Clippy, all three
executables, and byte-identical replay of their example JSON. A wrong scalar
witness and a composite modulus must fail. Stop on any mismatch and preserve
the diagnostic. No wall-clock comparison or IC candidate promotion is made.

The repository report and explanatory visual cite the source and artifacts.
Publishing is complete only when repository access allows a feature branch
to be pushed and a ready-for-review PR to be opened. Local checks and commits
alone do not satisfy that final requirement.
