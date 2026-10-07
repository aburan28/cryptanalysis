# One-target rho gate for square-based steered τ Z

## Frozen question

Does the opt-in square-based Z update preserve a complete single-target
rho solve when applied to both table batch evaluations and restarts?
Use one fresh public point derived by the independent affine fixture
generator. Run generic reference, existing `paired2-free-gauge-batch`,
and `paired2-free-gauge-square-z-batch` against that same point and rho
seed. Each invocation begins with an empty distinguished-point table.

The two steered arms must use the same scalar streams, prepared bytes,
τ and addition counts, rotations, gauge transitions, batch inversion,
restarts, walk, collision policy, budget, and recovered scalar. Every
nonidentity τ step in the new arm must count as square-based Z work;
the regular arm must count zero. The new arm must not alter the rho
trajectory against the generic reference.

The online clock starts with target-dependent solve work after input
and subgroup validation and ends after internally verified scalar
recovery. It includes target-dependent preparation, all table and
restart evaluations, batch normalization, walk and collision work,
including failed attempts. Fixture construction and process launch
are outside this clock. A separate post-solve scalar replay is kept.

Commit the implementation, unit tests, independent fixture generator,
checker, and strict isolation manifest generator before generating the
new target. Commit the target fixture in a second commit before any
solver invocation. Run `reference, regular, square Z, square Z,
regular, reference` serially in each of Release and UBSan. Preserve
all raw trials, failures, source and binary hashes, operation counts,
online timing, replay timing, and correctness evidence.

This local panel is a correctness and algorithmic diagnostic. Keep
`cpu_speedup_claim` and `isolation_receipt` null until a host-level
isolation receipt meets AGENTS.md. The formula is based on the known
Xu--Yu--Han--Lu Z identity; academic novelty and an end-to-end CPU
speedup are not established by this panel.
