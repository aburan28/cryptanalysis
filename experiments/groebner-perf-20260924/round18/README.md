# Independent packed equation evaluation and certification

This opt-in experiment removes Python coefficient dictionaries from original-
equation replay and per-equation term lists from independent certification.
Every public-point query still performs fresh native descent, the unchanged
producer, an independent exact basis certificate, two direct equation checks,
and full signed-point curve replay. Fixed workspaces contain only reusable
layout and scratch storage; numerical buffers are cleared on every certificate.
The existing default solver dispatch is unchanged.

Four arms isolate the changes on the same frozen inputs:

| Arm | Independent certificate | Original-equation replay |
| --- | --- | --- |
| `baseline` | round15 ordered direct-ANF checker | unchanged Python evaluator |
| `packed-replay` | round15 checker | native direct packed subset test |
| `zeta-certificate` | new independent packed bit-sliced evaluator | unchanged Python evaluator |
| `combined` | new evaluator | native direct packed subset test |

All arms use round17's native full-public-point curve replay for supported fields
and its explicitly labelled Python fallback for wider fields. The producer is
the existing exact-evaluation/Buchberger–Möller implementation, not F4 or F5.

## Exact checks and independence

The new checker accepts packed `(monomial mask, equation bitset)` coefficients
directly. A 64-bit word encodes direct evaluations of each monomial on the low
six variables. For each equation, a separate subset transform on the remaining
variable masks produces its truth table. The intersection of these independently
evaluated zeros supplies the roots for exact basis checking. Unordered input and
duplicate monomials are handled by XOR, without constructing sorted term rows.
All coefficient limbs and masks are validated before evaluation, including
equations that would be skipped after the zero set becomes empty.

The verifier has its own implementation and workspace, with no producer headers,
roots, pivots, transforms or completion flags as inputs. The basis checks are
extracted byte-for-byte from the SHA-256-pinned round15 reference: basis rows
vanish on the independently established input roots, the leading-monomial
staircase has the same dimension, leading terms are minimal, and tails are
standard. These prove equality and a reduced Gröbner basis in the Boolean
quotient with its field relations; see round3's certificate argument. The build
and audit both bind the generated checker fragments to that frozen source.

The replay evaluator separately applies the direct test `(mask & assignment) ==
mask` to the supplied packed coefficients. It does not consult the certificate's
truth table, including after failed certification. Both pre- and post-curve
equation checks remain present. The benchmark additionally charges the untouched
Python evaluator on the original frozen ANF to every successful arm. A separate
Python curve-witness audit is retained outside timing and labelled accordingly.

For `E` equations, `T` packed terms and `h=max(nvars-6,0)`, the transform performs
at most `E*h*2^(h-1)` 64-bit XORs (zero for `h=0`), plus coefficient decoding and
root intersection. Decoding visits the set bits of the supplied coefficients.
The truth scratch stores `E*2^h` words. This is an established subset transform,
not a novel F6 algorithm or an escape from exponential Boolean enumeration.
Sparse/early-rejecting cases may favor the previous adaptive checker, so the
four-arm complete-query comparison determines applicability.

Native checker limits are 1..20 Boolean variables and 1..128 equations. It checks
large zero sets exactly and omits the solution list above 256 roots. The unchanged
producer separately rejects more than 256 roots as inconclusive. The fixed
truth/root/presence buffers require at most 16,908,416 bytes at these limits;
reported `scratch_bytes` excludes basis vectors, Python storage and allocator
overhead, and is not a process memory peak. Calls on one Python handle are
serialized with destruction; different handles own separate workspaces. Input
arrays stay owned by the caller and must not be changed during a native call.
Raw C callers remain responsible for live handles, buffer extents and synchronization.

## Validation and measurements

The local suite covers 240 randomized certificate comparisons with the previous
independent checker and brute-force root enumeration, 7,328 direct equation
evaluations, shuffled/duplicate terms, high coefficient limbs, malformed ABI
inputs and every basis-rejection code. Optimized and UBSan trap checker builds
are tested. Zero and many-root ideals extend through 20 variables. Concurrent
calls on distinct inputs, sequential in-place mutations and repeated use test
freshness and closed lifetimes. Complete queries
compare all four arms over degrees 11, 31 and 83, replay explicit witnesses and
check original equations. Packed replay tests forbid dictionary conversion.
The producer and descent builds are unchanged; the sanitizer label applies to
the new checker and curve replay, not a newly sanitized producer.

The initial import-discovery failure and the subsequent random-fixture test that
exceeded the producer's existing root cap remain retained as failed attempts.
The final test treats that producer limit explicitly and checks larger zero sets
directly with the verifier. Test fixture timings used to exercise the audit are
synthetic and are not performance measurements.

Performance is pending an admitted measurement. The first local attempt rejected
load admission before any numerical query. CI attempts 31 shuffled repetitions
plus warmup on ten frozen controls, records all four arms and preserves rejected
admissions. Setup, fixtures, exact source/build identities, memory information,
per-query phases and independent audits remain in the report. Group-start and
final load must also satisfy the predeclared gate for timing eligibility. This
gate does not prove exclusive ownership of a virtualized host.

These are planted component controls. Candidate identity and IC/rho wall times
remain null. No natural relation yield, full discrete-log recovery, GPU win,
larger-ring capability or global performance ranking is inferred from this work.

## Reproduce

From the repository root, with Python >=3.10 and Clang or GCC:

```sh
python3 experiments/groebner-perf-20260924/round4/build.py
python3 experiments/groebner-perf-20260924/round14/build.py
python3 experiments/groebner-perf-20260924/round15/build.py
python3 experiments/groebner-perf-20260924/round17/build.py
python3 experiments/groebner-perf-20260924/round18/build.py
python3 -m unittest discover -s experiments/groebner-perf-20260924/round18 -p 'test_*.py' -v
python3 experiments/groebner-perf-20260924/round18/verify_evidence.py
python3 experiments/groebner-perf-20260924/round18/benchmark.py --repetitions 31 --output /tmp/packed-truth-new-run.json.gz
python3 experiments/groebner-perf-20260924/round18/audit.py /tmp/packed-truth-new-run.json.gz
```
