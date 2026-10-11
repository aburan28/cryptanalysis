# Public-target curve witnesses

This experiment moves the bounded curve-witness producer into portable C++17
and independently verifies its output with the existing Python field arithmetic.
It applies to the binary curve `y² + xy = x³ + b`, with odd field degree 3–63,
nonzero `b`, at most eight factors and at most 64 Boolean factor coordinates.
The Python reference remains available. This research adapter is not a
constant-time cryptographic API and is not enabled as a global solver default.

The native producer freshly lifts the supplied x-coordinates, enumerates signs
in the same order as the Python producer, and returns signed points plus a
point-addition chain and its slopes. The independent checker checks canonical
point encodings, each point's curve equation, factor coordinates, every group
law identity, the original polynomial equations and the **full supplied public
point**. Inversions, lifting and point addition are forbidden in a unit control
for this checker. A slope is checked by multiplication against its denominator.
Doubling, cancellation, infinity and x=0 each have explicit cases. The optional
search sign mask is diagnostic output, not part of the mathematical witness.

The native context is immutable and contains only validated field and curve
parameters. Each call owns a fresh result buffer. A Python lock covers both the
native call and close, preventing use-after-close. Native degrees above 63 are
explicitly unsupported; the independent Python implementation has no such
native-word degree limit within its declared factor-coordinate bound. No GPU
or architecture-specific instructions are involved.

## Timing contract

Both arms use the unchanged round62 packed F4 producer, independent algebraic
checker, round60 leased inputs and fresh target-dependent coefficient descent.
The baseline uses prepared Python curve-witness production. The candidate uses
native curve-witness production. **Both use the same independent Python witness
checker twice:** first against fresh equations, then against frozen equations.
Four exclusive phases sum exactly to each complete query wall interval.

This is a new, matched public-input comparison. Historical `verify_solution`
constructed a field (rechecking irreducibility) and reconstructed the target
from planted fixture points on every replay. This experiment performs ring-only
validation and fixture construction outside both timed arms. Removing those
costs must not be presented as a pure arithmetic speedup against older panels.
The independently supplied target is checked on-curve within the query.

`freeze_public_targets.py` is an offline fixture constructor and audit. It is
never imported by query execution. `PublicQuery` has no planted points or
planted assignment. The frozen inputs are still planted correctness controls,
not natural relation-yield observations, unseen-target DLP solves, or independent
population samples. Repeated fixtures sharing a target remain repeated controls.
`candidate_id` and full IC `online_speedup` remain null.

The frozen plan keeps the five six-variable primary cases, three trials of
seven measured pairs per case, randomized alternating arm order and one warmup.
All comparisons charge descent, conversions, solving, algebraic verification,
extraction, witness production, checking and lease teardown. CPU load admission,
all failures, all secondary cases and incomplete panels remain in the record.
No routing promotion follows a partial panel. A further 2× gain is a target,
not an acceptance assumption.

## Reproduction

From the repository root, using ordinary Python rather than Sage:

```sh
python3 -u experiments/groebner-perf-20260924/round63/run_validation.py --output /tmp/public-replay-evidence
```

The output directory must be new. This rebuilds the native libraries on the
current host, runs optimized and UBSan controls, preflights 92 query records,
attempts the frozen timing panel, and independently audits the artifact. CI
repeats this on native Linux x86-64 and hosted macOS ARM64. Artifact audit never
loads binaries compiled on another platform. A build receipt binds sources,
plans, public points, reference results, generated code, libraries and the
validated summation-polynomial resource. `RESULTS.md` records observed results.
