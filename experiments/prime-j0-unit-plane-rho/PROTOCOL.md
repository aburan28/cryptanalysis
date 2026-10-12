# Unit-coordinate plane for paired τ rho startup

## Frozen hypothesis

The existing paired2 evaluator rotates a prepared seed point's Montgomery
x-coordinate by `beta` or `beta²` whenever a width-four digit has a nonzero
unit power. Instead, store all three x-coordinates next to the one affine
y-coordinate for each of the 18 prepared seeds. Compute the two extra
x-coordinates once during target-dependent preparation. The evaluator then
selects a coordinate by the existing digit power. No new point additions,
inversions, lattice representatives, digit recodings, or pair scores are
allowed. The plain paired2 prepared object stays unchanged; the plane is
a separate opt-in format with its own byte count.

Combine this format with the existing eight-output batch normalization
in an opt-in `TAU_PAIRED2_PLANE_BATCH` rho startup mode. Compare it with
`TAU_PAIRED2_BATCH` on the same one-target point and seed. Both must use
the same scalar coefficients, multiplier points, restarts, distinguished
point table, cap, and verification. Count the extra preparation rotations,
the removed evaluation rotations, table bytes, one batch inversion,
reference-equivalent rho operations, and complete online wall time. The
predicted one-target net field-multiplication saving is evaluation
rotations minus preparation rotations; this does not itself prove a CPU win.

Use the earlier batch-rho fixture only for development. Freeze source,
unit tests, fixture generator and panel checker before deriving a fresh
public `glv-j0-32` target with independent affine Python arithmetic.
Run `reference,batch,plane,plane,batch,reference` serially, with one empty
rho table per invocation. Preserve every raw trial and failure. Require
correct scalar recovery and replay, identical target/seed echoes and rho
trajectory counters, equal τ/addition/recode work, and one table output
inversion in each candidate. Unit tests must cover both study curves,
zero/order-boundary scalars, identity, equal/opposite points, cancellation,
and batch output normalization.

Local CPU timings remain exploratory without the strict host-level
isolation receipt required by AGENTS.md. Keep the new path opt-in;
automatic routing and an academic novelty claim require further evidence.
