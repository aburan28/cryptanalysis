# Independent replay from public target points

This opt-in query accepts a public binary-curve point `(x, y)` and performs fresh
packed descent, native basis computation, independent Gröbner certification,
original-equation checks and full-point curve replay. It does not receive a
planted assignment or the fixture points used to construct the target.

The replay has two implementations: unchanged Python field/curve arithmetic
with reusable fixed field setup, and a native checker using the repository's
separate PDP field kernel. Both check the same public point, return explicit
signed point witnesses and use the same ordered CPU certificate path. The
implementation is correctness-tested. An admitted Linux CI run retained **640
verified complete queries**. Its six 18-variable controls improved by
**1.193–1.406×**, and its 9- and 12-variable GF(2^31) controls improved by
**5.033× and 5.097×**, respectively. These are paired wall-time geometric means
on one runner, not a global performance ranking or a full IC result.

The first local timing attempt was rejected before numerical work at a
one-minute load of 68.600 on 14 logical CPUs. It made zero timed attempts and
remains retained separately from the admitted Linux run.

## What changes at the query boundary

The earlier planted-control oracle reconstructed its reference point from
`Instance.points`, revalidated the field for each call, and accepted a signed
sum with matching x coordinate. This API takes the complete public point,
validates that point, and compares both coordinates of the sum. Field validation
and fixed trace/half-trace/square-root tables belong to reusable setup in both
comparison arms. Every target is validated afresh. Removing fixture construction
from timing is an accounting correction, not a measured algorithmic speedup;
new results must compare these two arms on the same new boundary.

The original `Instance.evaluate` method is retained directly for independent
ANF evaluation. On a successful result it is used before curve replay and again
afterward. Monomial coefficients arrive as the owned `PackedANF` output of
round14's native contraction, and round15's ordered independent decoder checks
the basis. Producer roots, transforms, pivots and fixture points are not inputs
to the curve checker. No existing solver dispatch changes.

`PublicQuery.solve` returns an explicit `curve_witness`: signed points, sign
mask and number of sign patterns examined. It also reports the public target,
actual replay backend, binary identities and exclusive target-validation,
descent, basis/certificate and equation/curve-replay nanoseconds. These phases
sum to its internal query interval. The benchmark additionally charges Python
call/return overhead and untouched reference-ANF evaluation in its outer wall
interval. Phase medians are diagnostics and must not be added to make a total.

## Native arithmetic and exact decision

The native replay uses `pdp-degree-heuristics/pdpkernel.c` for polynomial-basis
GF(2^n) arithmetic and the curve `y^2 + xy = x^3 + b`. It is independent of this
query's packed Boolean producer and coefficient contraction. Setup validates
the degree, nonzero curve coefficient and irreducibility before any inversion.
The C entry point runs Ben-Or's polynomial irreducibility test; it does not
depend on Python assertions for field validity.

For each supplied x, the checker computes one lift, rejects failed lifts and
checks every lifted point's curve equation. It enumerates all sign masks in
integer order and accepts exactly when their sum equals the full target. This
is exhaustive in the declared sign dimension, with at most `m * 2^m` affine
additions. No new asymptotic algorithm is claimed. The returned signed y values
allow a separate implementation to replay the witness directly.

The standalone replay supports 1..12 supplied x coordinates. Native fields must
have odd degree 3..63. The Python reference supports odd degree 3..127;
`native-or-python` explicitly selects and labels Python for wider fields, while
`native` rejects them. No even-degree half-trace claim is made. A zero curve
coefficient, reducible modulus, out-of-field coordinate, invalid public point
or noncanonical infinity encoding is rejected. Standalone replay supports
identity targets and identity intermediate sums; the descended query requires
a finite target because its input polynomial uses the target x coordinate.

Per-call coordinates, lifts, partial sums and output witnesses are fresh. The
native field context is immutable. Python locks serialize calls and destruction
on one handle; independent handles are separate. Raw C callers own valid handle
lifetimes and buffer extents. Outputs are cleared before validation, and invalid
inputs do not leave a previous successful witness visible. The library does not
impose a process timeout.

Curve replay proves the supplied points satisfy the curve equation and signed
sum. It does not independently establish a subgroup or factor-base catalogue;
integration into an IC pipeline must retain that pipeline's membership checks.

## Correctness evidence

The final combined suite passes all eleven tests in one discovery run, in
90.393 seconds on the busy local host. The earlier core suite passed eight test
groups in 33.120 seconds:

- 1,536 exhaustive native/Python comparisons over two curves over GF(8), with
  all pairs of x coordinates and every curve point plus the identity as target;
- 480 randomized native/Python comparisons over degrees 5, 11, 31, 61 and 63,
  two nonzero curve coefficients, planted witnesses and unrelated target points;
- optimized and UBSan trap builds, returned-witness replay, failed lifts,
  exceptional additions/doublings, the 12-point limit and identity sums;
- malformed native inputs, reducible fields, output reset, concurrent reuse,
  changed targets and closed lifetimes;
- complete public-point queries over degrees 11, 31 and 83, comparison with
  original ANF evaluation and the old planted-control oracle, and an explicitly
  labelled wide-field fallback;
- benchmark admission, preservation of existing evidence and load-based timing
  disqualification.

Three additional audit tests exercise report corruption, source/build identity
bindings, overload, incomplete evidence and retained work-limit failures. Their
temporary synthetic report fixtures contain explicitly artificial timings and
are not benchmark measurements. CI rebuilds and repeats the tests on Linux and
macOS. Source and build receipts provide reproducibility and integrity checks;
they are not external attestations.

The first CI run exposed older adapters changing the Python import search path,
which redirected combined discovery to round4's audit module. Imports and query
construction now restore the caller's search path, and the complete-query test
checks that invariant. The combined local run includes all core and audit tests.
The initial CI failure logs and initial build receipt remain separate artifacts;
the current receipt identifies the formatted native source used by the combined
run. No failed CI run is presented as passing evidence.

## Retained complete-query comparison

[CI run 36294322020](https://github.com/aburan28/cryptanalysis/actions/runs/36294322020)
measured head `2bf712a4d49e9ee4be13d2b539ca8e29d1546461` through its PR merge
checkout `07edabb083ff55f2f8b28bb77ce8979f114bf007`. The numerical replay sources
match the current code. Its Linux guest exposed four logical CPUs on an AMD
EPYC 9V45 host and ran Python 3.12.14. Load was 0.729 at admission and 0.915 at
completion, with all recorded group starts below the declared limit of four.
This establishes admission, not exclusive ownership of the physical host.

Each control has 31 shuffled paired measurements plus one warmup pair. All 640
attempts solved and independently verified, with matching basis certificates,
assignments and signed point witnesses across the arms. The report, source/build
snapshots, runner metadata, admission record, audit and GitHub run/artifact
metadata are retained under `results/ci-ubuntu-run36294322020/` and neighboring
receipt files. A local re-audit agrees with the CI audit.

| Control | Python median ms | Native/fallback median ms | Paired wall GM [bootstrap 95%] |
| --- | ---: | ---: | ---: |
| 18 variables, seed101 | 8.599 | 7.210 | 1.193 [1.189, 1.197] |
| 18 variables, seed102 | 9.252 | 7.142 | 1.304 [1.290, 1.326] |
| 18 variables, seed103 | 8.695 | 7.271 | 1.199 [1.196, 1.203] |
| 18 variables, seed104 | 8.761 | 7.249 | 1.206 [1.202, 1.210] |
| 18 variables, seed105 | 9.058 | 7.289 | 1.245 [1.239, 1.251] |
| 18 variables, seed106 | 10.407 | 7.426 | 1.406 [1.401, 1.410] |
| 9 variables, GF(2^31) | 2.042 | 0.404 | 5.033 [4.954, 5.102] |
| 12 variables, GF(2^31) | 4.278 | 0.837 | 5.097 [5.051, 5.143] |
| 6 variables, GF(2^11) | 0.378 | 0.240 | 1.526 [1.479, 1.570] |
| 6 variables, GF(2^83), Python fallback | 15.607 | 15.645 | 0.998 [0.993, 1.003] |

The ratios use paired observations, not ratios of marginal medians. The largest
gain occurs where curve arithmetic dominates the small Boolean solve. On the
18-variable seed101 control, equation/curve replay changes from a 3.474 ms
marginal median to 2.084 ms, while basis/certificate work remains around 4.5 ms.
The remaining replay includes Python packed-to-dictionary conversion and original
equation scans. The wider-field fallback remains near parity; no native speedup
is claimed there. These measurements use a new common public-point boundary and
must not be multiplied by gains from earlier rounds or directly compared with
their different busy-host absolute timings.

The same CI run's macOS guest rejected admission at load 10.347 against a limit
of three logical CPUs, with zero numerical attempts. Its metadata probe reported
an `Apple Paravirtual device` from Metal. That is device-availability evidence,
not shader execution, GPU correctness or a GPU speedup. Both the rejection and
device probe are retained under `results/ci-macos-run36294322020/`.

## Paired timing protocol and remaining limits

The benchmark predeclares the same ten planted component controls used in
round16: six 18-variable controls and four smaller/wider-field controls. The
target point and original ANF are frozen before either arm runs. Arms are
shuffled within each paired repetition. Each query constructs fresh coefficients,
solver state, certificate and replay witness; a workspace contains only reusable
fixed setup. Setup time, fixture time, host metadata and parent memory high water
are recorded separately. Per-query peak memory is not known.

Before fixture or numerical work, the default admission limit requires a
one-minute load no higher than the number of logical CPUs. Existing report or
admission paths cannot be overwritten. Group-start and final load are recorded;
excess load or interruption disqualifies timing eligibility without discarding
attempts. This necessary check does not prove exclusive CPU/GPU ownership.
Interrupted rows, exceptions and work limits remain evidence. A control with a
failed attempt receives no paired speedup claim in the audit.

Both arms' online intervals include their own independent complete curve replay.
An additional Python witness audit runs outside those intervals, and its cost
and result are recorded separately. This extra audit is not silently charged
to the native algorithm or represented as part of its online time.

The retained `paired-attempt1.json.gz.admission.json` records the rejected first
local attempt; there is no corresponding local timing report. The admitted Linux
comparison is a separate run. These controls do not measure natural
relation yield, recover discrete logarithms or qualify an IC candidate. Candidate
identity and IC/rho times remain null. The producer remains exact evaluation plus
Buchberger–Möller interpolation, with a 20-variable and 256-root limit. The
separate larger-ring algebraic certificate work and F4/F5 paths are unchanged.

PR CI also attempts a bounded 31-pair CPU comparison on its existing Linux and
macOS runners after correctness checks finish. The same predeclared load gate
applies: a busy runner preserves its rejection without numerical work. An
admitted run retains every attempt, source/build snapshot, paired audit and
runner identity as a downloadable artifact. Completing CI is not itself a
speedup claim; the complete-query results and their admission records must be
inspected. These jobs do not execute GPU benchmarks.

## Reproduce

From the repository root with Python >=3.10 and Clang or GCC:

```sh
python3 experiments/groebner-perf-20260924/round4/build.py
python3 experiments/groebner-perf-20260924/round14/build.py
python3 experiments/groebner-perf-20260924/round15/build.py
python3 experiments/groebner-perf-20260924/round17/build.py
python3 -m unittest discover -s experiments/groebner-perf-20260924/round17 -p 'test_*.py' -v
python3 experiments/groebner-perf-20260924/round17/verify_evidence.py
python3 experiments/groebner-perf-20260924/round17/benchmark.py --repetitions 31 --output /tmp/public-replay-new-run.json.gz
python3 experiments/groebner-perf-20260924/round17/audit.py /tmp/public-replay-new-run.json.gz
```

For library use, import `PublicQuery` from `public_query.py`, construct it with
the fixed `(n, modulus, b, m, ell)` and an explicit arm, and pass only a `Point`
to `solve`. Use a context manager or close it explicitly. No implicit compiler
invocation occurs at query time. A performance promotion must stay within the
measured workload/backend applicability; no existing default dispatch changes.
