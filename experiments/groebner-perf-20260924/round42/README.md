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
passing zero disables it. A replacement rejected by native modulus validation
leaves it disabled; Python argument-type/range errors occur before that request.
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

The portable package also passes 18,003 system runs (17,949 verified and 54
expected root-limit outcomes), four budget controls, seven configuration
controls and 54 complete queries. Its independent original-ANF audit passes
all 54 records and 35 unique proofs. Complete proof bytes, mathematical
outputs and integer work match the isolated physical prototype exactly.

The paired timing audit passes all 6,040 completed queries. Thirty-three of
36 planned trials qualify; two exceed the unchanged load limit and one is
not admitted. All three frozen 24-variable inputs pass both trial gates
against every retained comparator: 15.845–21.852 ms complete-query medians,
with paired gains of 1.303–1.441 over previous wide Metal and 1.861–2.689 over
the fastest measured CPU. Smaller inputs have no repeated combined-path win.
The 27-variable controls need qualifying repeats. See [results and limits](RESULTS.md)
and the frozen plans and full analysis in `evidence/`.

Earlier normalization timing retains 4,176 verified queries, only one
qualified trial and no repeated gain. This is a planted PDP-stage experiment
with `candidate_id: null`; a complete same-point single-target IC/rho
comparison remains a separate acceptance gate.
