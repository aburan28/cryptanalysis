# Guarded normalized certificates with optional wide Metal elimination

For supported quadratic residuals, this experimental producer removes repeated
quadratic elimination from affine-certificate construction. It checks that all
fresh quadratic columns share the declared invariant form, verifies a scalar
inverse, and transports a precomputed annihilator back to combinations of the
original equations. Small lookup tables represent that binary-linear transport
exactly. The existing independent checker receives the same certificate format.

The CPU path is portable; Metal execution is explicitly requested. The optional
GPU path combines this constructor with round41's 55-feature, 32-equation
residual elimination and fresh symmetry check. No global dispatch changes.

## Applicability and fallback

Normalization requires an explicit monic odd modulus, at most 31 equation
coordinates, a standard polynomial basis, at least three residual variables,
and `3*ell-4 < n`. Every quadratic column must match `alpha*Gamma`. The inverse
is accepted only after its product with alpha equals one. Zero alpha uses the
original affine subsystem. Unsupported shapes, mismatches and nonunits retain
exact projection/Macaulay/enumeration fallback. Work budgets include failed
normalization attempts, and resource limits never return a partial basis.

The [rank argument](RANK_LEMMA.md) establishes a dimension limit under explicit
assumptions. The [transport argument](TRANSPORT.md) justifies the lookup tables.
Neither is a general degree-of-regularity bound or a novel asymptotic result.

`normalized.Producer.configure_normalization(modulus)` enables the constructor;
passing zero disables it. Rejected replacement moduli leave it disabled.
`normalized_query.NormalizedQuery` configures it from the query's explicit field
description. Setup is target-independent; each solve computes fresh
coefficients, pivots, proofs, original-equation checks and signed curve replay.

## Reproduction

Use Python 3.12 or later and the native compiler for the machine being tested.
Build dependencies in rounds 20, 23 and 31 through 38 as in the dedicated CI
workflow, then run:

```sh
python experiments/groebner-perf-20260924/round42/build.py
python experiments/groebner-perf-20260924/round42/validate_native.py --output normalized-proof-evidence/correctness.json.gz
python experiments/groebner-perf-20260924/round42/audit_queries.py --input normalized-proof-evidence/correctness.json.gz --output normalized-proof-evidence/independent-audit.json
```

On macOS, add `--metal` to the build and validation commands to request the
actual device. A missing requested device is explicitly recorded; shader,
allocation and other backend errors fail validation. Wider equation counts
remain an explicit CPU fallback. There is no CUDA, OpenCL or HIP claim here.

The frozen corpus contains 6,001 exact systems. Optimized CPU and UBSan run all
of them; available Metal adds a third run. The suite includes normalization
guards, zero and nonunit scalars, high residual/equation words, symmetry changes
and expected root-limit outcomes. Transport controls test every supported
shape, all nibble entries, all toy-field values, output extents and modulus
replacement. Four low-budget controls check work accounting. Eighteen frozen
complete queries run on each selected backend/build. The independent audit
checks every complete-query proof against original ANFs without loading the
native solver, then verifies the reduced basis through the complete root set
and Boolean quotient dimension.

Build receipts record compiler, platform, source hashes and native binary
hashes. Hosted ARM64/x86-64 runs rebuild their own binaries. Hosted paravirtual
Metal results establish correctness for that backend, not physical-device
performance.

## Evidence status

The isolated combined prototype passed 18,003 system runs, four budgets and
54 complete queries on the physical M4 Pro. The independent original-ANF audit
passed all 36 optimized CPU/Metal records; UBSan outputs matched the audited
CPU reference. A preceding lookup-only prototype passed 24,526 transport cases
and retained exactly the same complete-query proof bytes as its reference.

Portable package validation and its binding to that prototype remain pending.
Per-input paired timings are running under a predeclared load gate with all
retained CPU/GPU comparators. No new repeated complete-query speedup is claimed
yet. Earlier normalization timing includes rejected/ineligible trials; those
outcomes remain in the evidence. This is a PDP-stage experiment with
`candidate_id: null`, not a complete single-target IC/rho result.
