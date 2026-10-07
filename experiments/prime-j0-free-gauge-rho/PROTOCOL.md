# One-target rho gate for unit-steered τ

## Frozen question

Does the opt-in unit-steered τ evaluator from
`experiments/prime-j0-free-gauge/` improve the complete startup path of
a single-target GLV rho solve? Use the same frozen public target and
rho seed for generic rho, `paired2-batch`, and
`paired2-free-gauge-batch`. Each invocation starts with an empty
distinguished-point table. The paired modes share the same two-neighbor
reduction, digit streams, 1,104-byte prepared table, eight-output batch
normalization, restarts, walk, collision policy, cap, and replay. The
new mode changes only the τ output Z constant and digit-coordinate
rotations, and must preserve the rho trajectory.

The online clock starts at the first target-dependent computation in
the solve after input/subgroup validation and ends when the scalar is
recovered and internally verified. It includes target-dependent τ
preparation, all table evaluations and restarts, batch-prefix products
and inversion, walk, collision, and failed work. A separate post-solve
scalar replay is retained. Fixture generation and process launch stay
outside the clock. The primary one-target rho reference uses the same
public point and resource envelope; local timing without a host-level
isolation receipt is exploratory.

Commit implementation, full unit tests, independent affine target
generator, checker, and isolated-run manifest generator before deriving
the new public point. Freeze the fixture in a second commit before any
solver invocation. Run `reference,paired2-batch,
paired2-free-gauge-batch,paired2-free-gauge-batch,paired2-batch,reference`
serially for Release and UBSan. Preserve all raw successes, failures,
code and binary hashes, startup and walk counts, free gauge changes,
online intervals, and replay timing. Require matching scalar and
trajectory counters plus the expected reduction in evaluation rotations.

The mode remains opt-in. A controlled CPU speedup or automatic routing
change requires a passing host-level isolation receipt and paired
repeat measurements under AGENTS.md. Academic novelty remains open.
