# Round 59: complete-query timing of column-indexed F4

This frozen panel measures round 58's incremental representation change against
its exact `chain_filter` baseline. It rebuilds both engines and the unchanged
independent checker. Every query constructs fresh coefficients, matrices and
certificates. Matrix-column conversion is inside the timed native solve.

The five frozen six-variable PDP controls are primary: three trials each, one
warmup and seven measured pairs per trial. The remaining 18 algebra/PDP controls
each receive one trial, one warmup and three pairs. Two arms across this fixed
schedule give 384 possible query executions including warmups. Arm order uses
predeclared seeded rotations. Round 57 retains the separate comparison with
other F4 variants and evaluation; this panel isolates the representation change.

The PDP interval starts with fresh target-dependent coefficient descent and
ends after root extraction, original-equation checks and curve replay. Native
ideal-membership and Boolean Gröbner-completion checks are inside this interval.
Fixture generation, ring-only layout construction and library loading stay
outside it. The separate Python certificate replay is offline validation.
Algebra controls are labeled separately; neither kind is a complete IC solve.

All four exclusive phase costs must be present and sum to the query time.
Incomplete phase accounting cannot produce a speedup claim. The frozen load
gate is one-minute host load no greater than the logical CPU count, checked at
admission and around each arm. Two rejected admissions end an attempt while
retaining all unrun cases. Failed/budget-limited results stay in the report and
cannot supply speedup denominators. Sources, binaries, integer traces and
preflight identities must remain unchanged.

Acceptance requires every primary trial to have seven verified measured pairs
and a descriptive paired-bootstrap 95% lower bound above one for
`baseline/indexed`. Reaching two is a separate engineering target. Intervals do
not provide familywise or population guarantees, and planted controls do not
estimate natural relation yield. A partial panel cannot promote dispatch.

`measure.py` reuses the unchanged round 57 admission/recording driver. Analysis
reuses its paired statistics with stricter phase-completeness checks. The build
receipt binds those shared sources as well as the complete query path.
The reference descent's polynomial cache is checked against fresh symbolic
construction before setup, hashed, and retained alongside native artifacts.

Run `python3 run_validation.py --output /absolute/new/evidence/directory`.
The directory retains setup, tests, 92 optimized/UBSan preflight records, one
measurement attempt, its analysis, rebuilt binaries and an independent portable
audit. The CI workflow rebuilds on Linux x86-64 and macOS ARM64. A native
correctness pass or an overloaded runner is not a speedup result.
