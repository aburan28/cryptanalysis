# Native execution of reusable descent contractions

This opt-in implementation moves the fixed Weil-descent contraction from Python
multiplication-table calls into a portable C++ loop. It also passes the resulting
packed ANF buffers directly into the existing small-ring solver and its separate
independent certificate checker. Every target gets fresh coefficients, solving,
certification and curve replay. There is no cache of solved targets.

On six frozen 18-variable planted PDP controls, the confirmation improves
**complete verified query wall time by 1.53–1.63x** over the existing round4
Python descent plan with packed native solving/checking. The original screen
supports the same direction. This is an incremental gain over the already
optimized plan, not over the much older equation-set path. It does not establish
another 2x, a global ranking, or a faster asymptotic algorithm.

## Complete-query confirmation

Each cell is one frozen target with 15 paired measured repetitions plus a retained
warmup, with shuffled arm order. The field is GF(2^31), three summands, six
Boolean coordinates each. Values below are milliseconds. The reported speedup is
the geometric mean of paired wall ratios, not the ratio of marginal medians.

| Control | Python-plan query median | Native-packed query median | Paired GM [bootstrap 95%] | Descent medians only |
| --- | ---: | ---: | ---: | ---: |
| seed101 | 23.666 | 14.236 | 1.596 [1.511, 1.680] | 9.660 → 0.290 |
| seed102 | 23.865 | 14.850 | 1.591 [1.496, 1.688] | 9.262 → 0.289 |
| seed103 | 19.635 | 13.262 | 1.529 [1.475, 1.587] | 8.464 → 0.327 |
| seed104 | 19.277 | 12.200 | 1.562 [1.486, 1.634] | 8.181 → 0.256 |
| seed105 | 19.940 | 11.991 | 1.595 [1.493, 1.690] | 8.813 → 0.291 |
| seed106 | 20.841 | 13.397 | 1.633 [1.523, 1.796] | 8.094 → 0.322 |

The additional 9- and 12-variable GF(2^31) controls improve by 1.356x and 1.451x
in confirmation. The GF(2^11) six-variable control improves by 1.187x, while the
GF(2^83) six-variable control improves by only 1.080x. Wide-field curve replay
dominates that last control. All ten final confirmation intervals lie above one,
but the host is not idle and these are observations on this particular workload.

Each complete run contains 480 verified attempts across ten frozen controls and
three arms. We retain three complete runs: the first packed-view screen, a refined
screen, and the confirmation, for 1,440 verified attempts including warmups. The
first implementation repeatedly iterated ctypes buffers during Python replay.
The final implementation creates one Python replay view per query, after native
solving/checking, with its cost still charged to that query. Earlier measurements
are retained separately, not pooled as repetitions of the refined implementation.

An additional confirmation was interrupted by an ENOSPC error on the Mac's
internal temporary disk. Its 118 persisted groups / 354 verified attempt records,
exact source snapshot and error log are retained as incomplete evidence; no
speedup is calculated from that prefix. The query group in memory at the failed
save has no persisted timing/result record. The worktrees were then moved to the
external SSD and the full confirmation was repeated. This relocation and the
interruption are recorded in `results/interruption.json`. No earlier record was
rewritten to appear complete.

The machine is an Apple M4 Pro with 14 logical CPUs, 48 GiB memory and Python
3.13.1. One-minute load endpoints were 60.2→49.3 for the first screen,
21.0→19.9 for the refined screen and 20.0→18.7 for confirmation. Per-pair load,
CPU time and all individual wall samples are retained. Confirmation used the
same source and compiled libraries after relocation; per-query binary-hash file
reads remain charged in every arm. Do not pool different runs to conceal these
environment changes or substitute CPU time for wall-time promotion.

## Timing boundary and correctness

All three arms start with the same supplied target coordinate. The charged
interval includes fresh descent, buffer/dictionary preparation, basis
computation, the independent coefficient decoder and exact truth/staircase
certificate, original equation checks, full curve replay and an additional
untouched reference-ANF evaluation. Descent, solve/checks and reference replay
are exclusive phases whose nanoseconds sum exactly to the recorded wall time.
Nested producer/certificate/extraction metrics are diagnostics, not extra costs
to add to that total.

Ring-only layout construction, field validation, library/workspace loading and
fixture generation are reported separately. The native setup is not free: for
the 18-variable shape, the confirmation records 487.728 ms for native plan and
library construction versus 95.108 ms for the existing Python plan, plus
467.094 ms to create the first solver/checker workspace. Later same-process
shapes have different load conditions; these are measured setup costs, not
amortized charges or universal constants. The 18-variable native layout holds
40 distinct multiplication tables (327,680 bytes), 14,099 edges, 10,582 total
numeric slots and 9,388 final support slots. Parent memory high water is retained;
per-query peak memory is unknown.

These are planted component controls, not ordinary relation-yield estimates.
The unchanged planted-control curve oracle reconstructs its reference target
from fixture points during replay; this work is charged. It is not yet a
public-point-only verification API. The solver itself consumes only the ANF.
There is no logarithm recovery, IC candidate identity or paired rho measurement;
`candidate_id`, `IC_online_ms` and `rho_online_ms` remain null. The existing solver
is exact evaluation plus Buchberger–Möller interpolation, bounded to 20 Boolean
variables and 256 solver roots. This change does not replace that algorithm,
change F4/F5 dispatch, provide a GPU result, or solve the remaining high-degree
regularity problem. It speeds up the descent stage shared by those experiments.

## Implementation and invariant

`NativeDescent` uses the unchanged `DescentPlan` builder to obtain only data that
is fixed by `(field degree, modulus, curve coefficient, summand count, subspace
dimension)`: contraction edges, multiplication-by-constant tables, buffer sizes
and final monomial masks. Target powers and initial coefficients are freshly
computed using the existing Python field arithmetic. C++ owns copies of all
layout data and reusable scratch storage. A lock serializes a shared plan;
separate plans may execute independently. Every numeric slot is cleared on every
successful compute call, including destinations that receive no contribution.

At each stage the Python algorithm XORs `table(source)` into a destination. The
native loop uses the identical byte-sliced linear map, represented by one or two
64-bit limbs. Given identical source coefficients, every edge adds the same
field value. Induction through the stage order therefore gives identical final
coefficients. Zero coefficients are dropped in the same support order. Tests
compare the result with both the old plan and the untouched symbolic descent,
including repeated zero targets after nonzero targets.

The ABI validates stage offsets, source/destination/table indices, unique output
masks, field-bit bounds and output capacities before use. It supports field
degrees 1..128 and Boolean masks 1..20, with at most four stages, one million
edges, two million scratch slots and 256 MiB of native multiplication-table data.
These limits bound the native layout; the existing Python layout builder's setup
memory is separate. Calls are synchronous and have no hard wall timeout.
Invalid calls report errors with output count zero, and a following valid call
resets the full numeric state. Characteristic-two duplicate edges cancel.

`PackedANF` owns each query's output buffers. A later query or closing the plan
cannot overwrite them. Its buffers are internal query data and are not intended
for caller mutation. The input adapter supplies those buffers to the unchanged
round4 solver and independent checker without expanding equations or repacking
a dictionary. The unchanged Python equation/curve replay obtains one lazily
materialized dictionary view; that conversion is charged to replay, not hidden
in setup. The direct dictionary arm remains as an ablation and is sometimes as
fast as the packed arm at the whole-query boundary.

## Validation and reproduction

Four test groups passed locally on the current base in 8.019 seconds before the
replay-view refinement; the final validation log records the repeated qualified
run after that refinement. They cover 80 exact coefficient comparisons across
ten shapes in optimized and UBSan trap builds, field boundaries at 63/64/65 and
127/128 bits, m=2/3/4, 32 concurrent queries, owned-output lifetime, zero/nonzero
state resets, invalid targets and ABI layouts, duplicate-edge cancellation,
independent basis certificates, certificate rejection after equation mutations,
and the original curve replay. Small complete cases also use the separate Python
truth/staircase oracle. The independent solver and certificate implementation
are unchanged.

From the repository root, with Python >=3.10 and Clang or GCC:

```sh
python3 experiments/groebner-perf-20260924/round4/build.py
python3 experiments/groebner-perf-20260924/round14/build.py
python3 -m unittest discover -s experiments/groebner-perf-20260924/round14 -p 'test_*.py' -v
python3 experiments/groebner-perf-20260924/round14/verify_evidence.py
python3 experiments/groebner-perf-20260924/round14/benchmark.py --output /tmp/native-descent-new-run.json.gz
```

Every report embeds its exact measured source bytes and their hashes, build
receipt, frozen public-coordinate/ANF/curve fixtures, shuffled order and outcomes.
The evidence audit verifies those bytes, workload identities, repetition
coverage, independent-check flags, matching bases/assignments, reference-equation
replay and exact phase accounting before deriving ratios. Inventories seal the
live experiment and retained evidence; they are integrity records rather than
external attestations. Linux/GCC and macOS/Clang CI build and validate the current
implementation without using CI timing to claim a speedup.

## Next bottleneck

In confirmation seed 101, median native-packed certificate time is 7.160 ms and
extraction/replay is 5.109 ms, while the native solve/materialization interval is
1.119 ms. Marginal medians need not sum. These measurements put independent
verification and replay ahead of further basis-kernel micro-optimization for this
path. The next experiment should preserve their checks while reducing their
conversion/arithmetic cost, then compare a GPU verifier at the same complete
single-query boundary. High-degree algebraic proof work and structural F6
hypotheses require separate difficult controls and are still unfinished.
