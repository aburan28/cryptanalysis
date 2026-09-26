# Cached basis leaders and exact reduction experiments

This opt-in experiment removes repeated leading-monomial scans from the sparse
Boolean F4 producer. It also retains earlier irreducible-prefix and divisor-index
experiments, including their inconclusive and negative results. The separate
round11 algebraic verifier is unchanged. Production dispatch is unchanged.

The confirmation shows less CPU work on the same algorithmic trace, but the two
complete-query runs do **not** establish a general 2x improvement. Evaluation and
interpolation remains faster on every small planted PDP control here. All four
hard algebra controls and all 9/12-variable F4 PDP controls still exhaust their
work budget. Their reduced time to exhaustion is not a solved-query speedup.

## Actual profile and implementation

Round12 retained the original producer's sampled stacks. Disassembling the exact
sampled binary located the hot `Engine::normal +196/+200` instructions in its
repeated leading-monomial scan across reducer terms. The binary and source hashes
and disassembly are retained in `results/sampled-normal-*`. This corrects the
initial hypothesis that the divisor scan itself dominated those samples; the
receipt is a profiling diagnostic, not a performance measurement.

`cache_transform.py` adds one leading mask per installed basis row. Normal
reduction, symbolic matrix preprocessing, pair construction and installation use
that cache. Installation appends it, interreduction updates or removes it with the
row, and final sorting rebuilds it. Non-basis reducer vectors still compute their
own leaders. Tests compare the cache with fresh scans after installation,
interreduction, sorting and budget exhaustion. Cache storage is eight bytes per
basis row plus vector overhead. Every compute call constructs a fresh Engine;
there is no reuse of numeric basis data or target answers across queries.

The build applies checked transformations to hash-pinned engines and the
unchanged round11 packed ABI adapter. It builds these six producer variants, each
optimized and with UBSan trap instrumentation:

| Variant | Changes from the frozen round5 producer |
| --- | --- |
| `baseline` | Original implementation, transported through the round11 packed ABI |
| `ordered` | Round12 persistent monomial order and matrix pivot-key sorting |
| `frontier` | Ordered variant plus an irreducible-prefix cursor |
| `indexed` | Frontier plus a per-reduction bitset divisor index |
| `cached` | Frontier plus maintained basis leading monomials |
| `cached_indexed` | Cached variant plus the optional divisor index |

The experiment wrapper defaults to `cached`; this does not change any application
or earlier experiment's default. All variants use the same native independent
checker, and tests also invoke the separate Python checker and small-ring
truth/staircase oracle.

## Why the skipped work is valid

At the beginning of each normal reduction, terms are sorted by descending graded
reverse lexicographic order. Reducers and their priority remain fixed during that
call. Suppose a reducer has leading monomial L, a tail T < L, and we reduce a
term M divisible by L. The square-free multiplier Q = M \ L is disjoint from L.
Then T union Q < L union Q:

- If deg(T) < deg(L), taking unions cannot give the tail equal or larger degree.
- If degrees are equal and T intersects Q, its union has strictly smaller degree.
- Otherwise Q is disjoint from both, so adding the same mask preserves the
  highest differing bit and therefore the reverse-lexicographic order.

Every introduced term is consequently strictly below the term being reduced.
An already irreducible higher prefix remains unchanged and irreducible, so its
cursor survives the merge. Arbitrary Boolean multiplication does not preserve
order: L=1, T=2, Q=1 is a retained counterexample when disjointness is dropped.
The general argument is supplemented by 507,738 exhaustive triples through eight
variables; these finite checks alone are not a proof for all masks.

The optional index first probes eight reducer priorities. For more than 64
reducers it lazily records, for each variable, which priority ranks require it.
Intersecting the complements for variables absent from the queried term leaves
exactly the dividing leaders. The first set bit selects the original first
reducer, including skipped rows and stable priority ties. Small contexts use the
scalar scan. The index belongs to one fixed reduction context only; it is never
reused after reducers change. Index storage is 64 * ceil(reducers/64) 64-bit words.

Skipped logical comparisons are still charged to the original work budget.
`charge_ones_product` checks multiplication by division before adding, including
UINT64_MAX boundaries, and on exhaustion consumes exactly the units that the
original repeated `charge(1)` calls consumed. Ordinary `charge(amount)` retains
its original all-or-nothing behavior. Basis, derivation DAG, row/pair counts,
status, reason and logical work are identical in the parity tests.

## Measurements and limits

All five retained runs use the same 23 frozen inputs: eight algebra controls and
15 planted PDP controls at 6/9/12 Boolean variables, seeds 1..5, over GF(2^31).
The structured algebra and six-variable PDP cells have 15 measured repetitions;
the predeclared hard controls have three. One warmup per arm/case is retained but
excluded from summary medians and paired intervals. Arm order is shuffled with a
fixed seed. No failures or warmups are silently dropped.

| Retained run | Proof arms | Attempts including warmups | Verified | Inconclusive |
| --- | --- | ---: | ---: | ---: |
| `frontier-only` | baseline, ordered, frontier | 720 | 552 | 168 |
| `index-screen` | baseline, ordered, frontier, indexed | 920 | 696 | 224 |
| `index-confirmation` | baseline, ordered, frontier, indexed | 920 | 696 | 224 |
| `screen` | baseline, frontier, cached, cached_indexed | 920 | 696 | 224 |
| `confirmation` | baseline, frontier, cached, cached_indexed | 920 | 696 | 224 |

Each PDP cell additionally measures the existing evaluation/interpolation solver.
There are 4,400 attempts total: 3,336 verified and 1,064 inconclusive. The earlier
frontier/index measurements are separate experiments, not extra repetitions of
the later cached variant. Their exact source snapshots and build receipts are
retained, including when the experimental harness evolved between runs.

Final confirmation, complete verified six-variable PDP wall time in milliseconds:

| Control | Original median | Cached median | Paired original/cached GM [bootstrap 95%] | Evaluation median |
| --- | ---: | ---: | ---: | ---: |
| pdp-6-seed-1 | 10.833 | 8.073 | 1.299 [1.001, 1.682] | 1.450 |
| pdp-6-seed-2 | 15.837 | 11.670 | 1.311 [1.016, 1.672] | 1.299 |
| pdp-6-seed-3 | 5.539 | 3.139 | 1.441 [1.101, 1.858] | 1.626 |
| pdp-6-seed-4 | 9.060 | 11.311 | 0.888 [0.703, 1.118] | 1.173 |
| pdp-6-seed-5 | 11.739 | 7.347 | 1.506 [1.165, 1.884] | 1.179 |

Four cached confirmation intervals lie above one; the earlier screen does not
reproduce a consistent improvement across these five cells. The selected machine
was not idle: it is an Apple M4 Pro with 14 logical CPUs and 48 GiB memory, with
one-minute load 37.6–41.5 during the cached screen and 46.9–50.7 at the confirmation
endpoints. Per-row load and parent CPU time are retained. CPU time is diagnostic;
it cannot replace wall time for promotion. No single calibration ratio removes
this contention, and bootstrap intervals do not account for all nonstationarity.

For example, the nine-variable seed-1 F4 control falls from median 374.615 ms to
90.553 ms of parent CPU time in the confirmation, with exactly the same logical
trace and work-limit failure. Both executions are inconclusive. Reporting that
ratio as a verified solver speedup would be incorrect. The divisor index's
incremental benefit is mixed; it remains a separately selectable experiment.

Timing boundaries:

- Algebra begins with identical frozen packed ANF coefficients and includes input
  packing, production, transport, independent checking and materialized basis.
- PDP begins at the supplied target coordinate and includes fresh descent,
  packing, solve/certification, bounded root extraction, independent original
  equation evaluation, curve replay and untouched reference-ANF replay.
- Ring-only descent plans and library loading are separate reusable setup.
  Fixture generation is outside all arms. Target coefficients and numeric solving
  state are fresh. Root extraction here scans at most 4,096 assignments; wider
  algebra certification is not a claim of non-enumerative root finding.
- Every proof arm gets 20 million producer work units, 500,000 DAG nodes, 4,096
  rows, batch 64, 20 million checker work units and 2 million retained terms.
  These are in-process work limits, **not a hard wall timeout**. Failed attempts
  retain partial timing and counters. Process memory high water is recorded;
  per-case peak memory is unknown.

These are component and planted correctness controls, not natural relation-yield
estimates or full IC executions. `candidate_id`, `IC_online_ms` and `rho_online_ms`
remain null. There is no recovered discrete logarithm, rho comparison, GPU claim,
F5 signature proof, global performance ranking or new asymptotic result here.

## Validation and reproduction

The local run passed ten test groups in 22.520 seconds. It checks all six variants
in optimized and UBSan builds, 96 random verified systems, exact successful DAGs
and all non-time counters, four hard work-limit controls, every work boundary
0..500 on a frozen case, node/row/batch limits, 64-bit masks, Boolean cancellation,
empty/unit ideals, repeated calls and 32 concurrent query tasks. Native tests
cover 135,178 bulk-charge cases, 6,480 indexed-divisor cases and 292 cache states
per build. The independent certificate checker is not changed or replaced by a
producer agreement test.

From the repository root, with Python >=3.10 and Clang or GCC:

```sh
python3 experiments/groebner-perf-20260924/round13/build.py
python3 -m unittest discover -s experiments/groebner-perf-20260924/round13 -p 'test_*.py' -v
python3 experiments/groebner-perf-20260924/round13/verify_evidence.py
python3 experiments/groebner-perf-20260924/round13/benchmark.py --output /tmp/cached-reduction-new-run.json.gz
```

The workflow repeats correctness and evidence checks on Linux/GCC and
macOS/Clang; CI is not used to claim a speedup. `results/summary.json` is regenerated
by `audit.py`, which verifies frozen workload/source hashes, complete arm and
repetition coverage, exact proof-arm logical counters, verified basis and root
agreement, and failure retention before calculating any paired speedup. The
inventory seals source and evidence files; it is a local integrity record, not
an external attestation.

## Next decision

Keep the cache available for larger algebraic experiments and retain evaluation
as the small-ring reference. Profile descent, independent verification and curve
replay on the fastest complete path before changing them. A GPU or structural
algorithm must then win one complete independently verified query, including
conversion, launch and checking costs, before dispatch changes. Hard unsolved
controls stay in every comparison, and the larger IC acceptance gate remains one
unseen public target through verified recovery with a paired rho measurement.
