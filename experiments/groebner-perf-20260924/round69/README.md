# Independent multiplier identities on Metal

This standalone experiment targets the round68 profile's independent
affine-multiplier check. It is not yet connected to the complete query path.
The existing checker and CPU dispatch defaults are unchanged.

Every selected proof record claims an exact identity in the Boolean quotient:
the sum of affine multipliers times quadratic original equations equals one.
The output degree is at most three. The GPU checks every degree-zero through
degree-three monomial, without random sampling or trusting producer pivots,
rows, coefficient tables or elimination state. Its factored coefficient
formula is derived in [round48's protocol](../round48/PROTOCOL.md).

Two explicit layouts are compared:

- `metal_record`: one GPU thread checks all output coefficients of one record.
- `metal_coefficient`: one thread checks one output coefficient; adjacent lanes
  gather the same feature from neighboring selected branches. Each record's
  first failing numeric mask is reduced with an atomic minimum.

The CPU comparator uses round48's factored/local evaluation with an invariant
layout prepared at setup. It additionally reports the first failing mask and
processes every selected record, matching this stage API. A separate dense
numeric-mask multiplication oracle checks every materialized coefficient.
The comparator is not a new measurement of the unchanged full-query checker.

## Inputs, lifetime and accounting

The coefficient table has the independent checker's feature-major order and
native 32-bit or 64-bit packing, up to 128 equations. Each call validates
dimensions, extents, alignment, sorted unique branch indices and witness
equation bits. Unused coefficient storage bits cannot contribute because the
corresponding witness bits must be zero. Output/input overlap is rejected.
All coefficient and proof inputs must remain immutable for the synchronous
call; caller-owned output storage must remain valid and private to that call.

The first prototype uploads the complete independent coefficient table,
selected witnesses and indices on every nonempty call. It freshly initializes
each result, submits an ordinary Metal command, waits, and copies results back.
No coefficient or answer reuse is implemented. Only layouts, pipelines and
allocated buffer capacity persist. Shared buffers use tracked hazards and
calls on one context are mutex-protected. Resource ordering follows Apple's
[Metal synchronization guidance](https://developer.apple.com/documentation/metal/resource-synchronization).
Destruction requires the owner to have joined all callers.

Empty record sets execute no device work and copy no data. Shapes require
1–20 fixed variables, 1–10 residual variables, at most 30 total variables,
and 1–128 equations. Coefficient and witness payloads each have a 64 MiB cap;
capacity cannot exceed the branch count. Optional materialized output has its
own 64 MiB cap and is used for coefficient-by-coefficient correctness checks.
The logical resident payload is retained separately from process memory.

All records execute even after a failing identity. Statistics report total
coefficient checks, the first invalid record, and records executed afterward.
This is actual batch work, not the sequential full checker's failure-prefix
accounting. Integration must retain that distinction. Per-call validation,
fresh uploads, result initialization, command encoding, submission/wait,
readback and result accounting are inside the stage wall interval. Nested
device time must not be added again. Context and pipeline setup, input loading,
original-ANF reconstruction, selection of symmetry representatives and separate
exact comparisons are outside it and are explicitly retained.

## Validation and diagnostic

The portable and physical-GPU controls span all residual dimensions, equation
boundaries 1, 31, 32, 33, 63, 64, 65, 127 and 128, sparse and dense data, exact
cross-limb cancellation, valid nonlinear products, a cubic-only counterexample,
fresh repeated calls, mixed failures, large atomic reductions, the exact
64 MiB table limit, malformed metadata, output aliasing, empty inputs and
concurrent callers. Optimized and UBSan builds run the same controls. UBSan
instruments host code; exact output comparison checks GPU arithmetic.

Three frozen original-ANF fixtures and full proofs come from round68's audited
snapshot. They select 0, 992 and 37,768 multiplier records. `inputs.py` verifies
original-input symmetry and identical proof aliases before selecting the
records that the independent full checker actually checks. It reconstructs
coefficients from original ANF with a feature-major descending subset transform.
The artifact auditor independently reconstructs every coefficient by direct
superset expansion, replays the full proofs (including constants and partial
certificates), and verifies the exact Boolean bases. It never loads retained
native libraries or executables.

The diagnostic uses all six CPU/GPU arm permutations repeated three times:
18 observations per arm, plus an explicitly retained warmup. Every observation
checks its complete result against the dense oracle. Both builds are retained;
sanitized timings are correctness diagnostics. An unavailable requested Metal
device remains an explicit result; CPU-only runs retain only the CPU arm at
its original positions. Actual availability is distinct from compilation.

```sh
python3 experiments/groebner-perf-20260924/round69/build.py --metal
# Commit the complete source and fixtures before a measured run.
python3 experiments/groebner-perf-20260924/round69/run.py --physical-hardware --output /absolute/new/evidence
python3 experiments/groebner-perf-20260924/round69/audit.py --evidence /absolute/new/evidence --output /absolute/new/audit.json
```

Use `--physical-hardware` only on a known physical untranslated host. Omit
`--metal` for a portable build; `--allow-unavailable` retains an unavailable
requested device instead of failing the run. Linux/macOS CI rebuilds each
platform separately. All ordinary-host timings are exploratory,
`timing_eligible` is false, isolation receipts are null and aggregate speedup
is unknown. A successful stage diagnostic does not establish complete-query
improvement, a CPU/GPU crossover, a new F4/F5/F6 algorithm, or a one-target
IC/rho result. Integration and a fully charged isolated comparison remain
necessary before changing dispatch policy.
