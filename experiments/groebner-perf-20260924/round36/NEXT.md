# Next: fixed-width deferred elimination

Keep this initial round36 source and its audited negative evidence immutable.
Use a separate branch/round for the follow-up so both implementations remain
available as paired ablations. The six-variant exploratory source generator is
archived in the local `deferred-affine-proof/kernel-pilot/` evidence directory.

Start with the smallest promising change: instantiate the affine elimination
function for one, two and three coefficient words and dispatch once per fresh
residual system using the validated layout. This allows constant loop bounds
and addresses the observed CPU generation cost. Keep proof reconstruction,
source IDs, work budgets, wire format and the independent checker unchanged.
Retain the source-index packing and full-shape variants as pilot evidence;
neither needs to be included in the first production candidate.

1. Make the dispatch and template bounds explicit, preserve the portable CPU
   path, and fail safely on impossible internal dimensions. The residual
   dimension bound 1..10 gives at most 176 cubic columns and three words.
2. Carry the existing 37 test groups forward and retain the all-dimension,
   equation-width and complete-proof comparisons from the pilot. Rebuild on
   each claimed backend; test small inputs, asymmetric inputs, high columns,
   cancellation, stale-workspace reuse and all forced budget fallbacks.
3. Pair old expanded enumeration, affine provenance, symmetry, initial deferred
   provenance, and fixed-width deferred provenance on the same frozen inputs.
   Keep direct complete-query comparison to the older baseline so any eventual
   4x claim is measured in one trial, not multiplied from separate ratios.
4. Predeclare two performance trials with the existing small/wide repetitions,
   load gate and timing boundary. Retain ineligible trials and failures. Run
   no local builds, tests or offline mathematical audits concurrently with
   timing. Use new shuffled arm orders with their seed in the report.
5. Independently audit original equations, complete proofs, roots, bases, curve
   witnesses, work counts, capacities, source/build receipts and journals. Only
   propose promotion after repeated qualified full-query gains and acceptable
   behavior on the smaller controls. Open a PR and merge only after the tested
   head passes CI and all actionable review findings are resolved.

The initial pilot establishes CPU evidence only. The subsequent GPU experiment
should first compact symmetry representatives within one query, then separately
test bounded affine-certificate generation with exact provenance. Charge
conversion, launch, synchronization, proof expansion and independent checking.
Requested Metal fallback is not GPU execution, and no CUDA/other-device speedup
follows from the Apple measurements.

The broader research gates remain separate: compare general high-regularity
systems against F4/signature and evaluation/interpolation methods at equal
output/completeness requirements; test structural reformulations before making
a novelty or asymptotic claim. Complete same-point single-target IC/rho
qualification also remains open and cannot be inferred from planted PDP
component controls.
