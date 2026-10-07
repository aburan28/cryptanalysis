# Opt-in paired-lattice rho startup: one-target gate

## Frozen question

Does the two-neighbor paired lattice evaluator from PR #425 preserve a
complete j=0 Pollard-rho solve when used for target-dependent multiplier
table points and walk restarts? Compare it with the existing generic
startup on the **same single public target point and frozen rho seed**.
This is an exact-solver integration gate, not a CPU speedup claim.

Add an explicit opt-in API. The default `ca_curve_solve` remains the
reference. Unsupported curves must return `CA_ERR_UNSUPPORTED` for the
opt-in mode; they must not silently run the default path. The `P,Q`
subgroup checks already made by `ca_curve_solve` precede both variants.
The candidate prepares the common 18-point table once after the target is
known, uses the paired2 evaluator for each rho multiplier and restart,
and records its τ maps, mixed adds, rotations, inversions, recodings, pair
scores, preparation, table evaluations and restart evaluations.

The existing rho runaway cap and `ca_stats.group_ops` use the same
**reference-equivalent budget units** in both arms. For a replaced
`aP+bQ`, charge the exact operations the previous two right-to-left
generic scalar multiplications and final group addition would have made.
Keep actual candidate point operations in separate startup counters; do
not interpret `group_ops` as physical candidate work. This preserves the
walk schedule and cap for a fixed seed and lets the test assert identical
collision trajectory statistics.

## One-target panel

Freeze one `glv-j0-32` public target point, its known-scalar fixture
certificate, and one nonzero rho seed before execution. Fixture scalar
construction is outside the timed interval. Each invocation solves only
that point from an empty table. Alternate reference and candidate in
ABBA order, retaining each raw result and all failures. Require recovered
scalar, independent replay, identical table entries and budget operations,
and exact target identity fields. Other small-curve targets may be unit
correctness controls, not an amortized baseline.

The online clock begins at the first target-dependent rho computation
after input/subgroup validation and stops after scalar recovery and the
rho solver's independent replay. Report a separate replay check after
the interval. The local panel is exploratory without a host-level CPU
isolation receipt from `docs/ISOLATED_BENCHMARKS.md`. Prepare a manifest
compatible with that runner, but do not claim a speedup or enable
automatic routing until a strict receipt passes. Academic novelty is
still unproved.
