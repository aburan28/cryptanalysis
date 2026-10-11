# Compact exact symmetry dispatch on Metal

This experiment implements [round37/NEXT.md](../round37/NEXT.md). After each
fresh coefficient-wise exact symmetry check, the GPU reduces one canonical
representative of each exchange-symmetric fixed-block pair. For 12 fixed
variables, it dispatches 2,080 branch reductions instead of 4,096. This is a
work-count reduction, not a measured complete-query speedup.

An immutable workspace map enumerates exactly `branch <= swap(branch)`,
including every diagonal once. The GPU writes reduced rows and full
contradiction witnesses at the original branch offsets. The host preserves
complete proof/root expansion and the unchanged independent round34 checker.
Odd fixed dimension or failed symmetry uses the full grid. All lanes of a
SIMD group take the same map/guard path before any collective. The host never
consumes stale alias output.

The implementation retains full input/output buffers to isolate scheduling.
The parameter block is 16 bytes. Map storage is four bytes per canonical
branch for even fixed dimension, or a four-byte bound placeholder for odd
dimension. Native workspace accounting includes these allocations once.
Map creation belongs to invariant setup; every query still transfers fresh
coefficients, updates dispatch parameters, generates proofs and checks them.
No specialized coefficients, numerical pivots or answers are reused.

The portable CPU producer remains the round37 fixed-width algorithm. Requested
Metal is supported through 31 lifted features and 32 equations. Wider shapes
retain explicit CPU fallback. The 24/27-variable controls therefore do not
establish GPU execution of the affine-certificate stage. CPU stays the default.

## Correctness and measurement

The final source-bound build passes 41 local test groups on the physical
Apple M4 Pro: 29 native/query/reference/scheduling groups and 12 auditor groups.
Coverage includes every three-variable Boolean function, 128-equation inputs,
UBSan, exact full-grid proof equality, complete queries through 27 variables,
mixed symmetric/asymmetric reuse, diagonal and padded groups, odd dimensions,
malformed proofs, forced work/copy/reconstruction fallback, source binding and
actual GPU-work accounting. A synthetic comparison rejects a candidate that
beats its immediate GPU predecessor but loses to an older GPU implementation.

The complete-query harness retains all earlier CPU/GPU arms. The auditor
requires fresh equations, complete roots and reduced bases, full original-ANF
proof identities, curve witnesses, exact work/capacity counts, source/build
receipts and hash-chained journals. It compares compact Metal against both
the fastest paired CPU and the fastest actually executed previous GPU. CPU
fallback cannot count as a GPU win. Repeated qualified trials are still
required; correctness alone does not establish a performance improvement.

Run ordinary Python; these jobs do not import Sage. Build rounds20,23 and
31 through38 in order. On macOS, append `--metal` to the builds for rounds31
through38 and set `QUADRATIC_TEST_METAL=1` for tests. Run the test suite with:

```sh
python -m unittest discover -s experiments/groebner-perf-20260924/round38 -p 'test_*.py' -v
python experiments/groebner-perf-20260924/round38/measure_compact.py --correctness-only --repetitions 2 --output correctness.json.gz
python experiments/groebner-perf-20260924/round38/audit_compact.py correctness.json.gz
```

Append `--metal` to measure requested Metal arms and `--large-controls` for
21/24/27-variable controls. Physical timing uses two predeclared small and two
wide trials, separate arm-order seeds and the unchanged load gate. Failed and
ineligible records stay in the evidence. Full query costs include fresh packed
descent, proof generation/copy/hash, independent certification, original
equations and curve replay; fixed setup and extra offline audits are separate.

These planted PDP controls retain null candidate/IC/rho fields. They establish
neither natural relation yield nor a complete IC recovery result. General
high-regularity F4/F5, novel F6 asymptotics, CUDA and untested-device claims need
separate evidence. [The next experiments](NEXT.md) isolate wider GPU constant
elimination, affine certificates and symbolic-elimination hypotheses.
