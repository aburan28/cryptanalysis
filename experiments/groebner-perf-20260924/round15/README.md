# One packed monomial order for independent certification

This opt-in decoder orders packed monomial indices once per query, then decodes
each Boolean equation in that order. The independent core skips its row sort
only after checking sortedness. Duplicate terms still cancel by parity, malformed
input is still rejected, and the complete input zero set and reduced Gröbner
basis checks remain unchanged. The solver, native descent, equation replay and
curve replay are unchanged. No default dispatch is promoted.

The motivation is a retained sample of the round14 independent certificate on
the 18-variable, 31-equation, seed-101 control. Of 2,304 main-thread samples, 862
(37.4%) were under repeated row sorting; the entire unpacking call had 1,053
(45.7%). These inclusive counts overlap and must not be added. All 457 repeated
certificates returned verified with six roots. This repeated-input profile is
not a query throughput benchmark. Its raw stacks, complete input/basis, binary
and source receipt, script and process results are in `results/profile/`. The
archived script retains its original absolute worktree path; it is a historical
observation artifact and is not run by CI.

## Exact implementation and three arms

| Arm | Packed decoding | Independent row unpacking |
| --- | --- | --- |
| `baseline` | Frozen original, one scan per equation | Original unconditional sort |
| `row-check` | Same frozen decoder | Check sortedness, then sort if needed |
| `ordered` | Validate all masks/coefficients; sort indices once only if masks are unordered | Same checked sort as `row-check` |

`reference/` contains the byte-for-byte original sources from merged commit
`7a3ac6d`. The builder verifies their fixed hashes and generates the core with
exactly one asserted source replacement. It preserves all other core code.
Build receipts retain compiler commands, generated-source hashes and binary
hashes. The Python factory changes only the independent checker library in an
existing round14 packed query. It does not consume solver roots as a truth set.

Each equation selects the same multiset of monomials before and after reordering.
Sorting that multiset yields the same row; cancelling identical masks by odd/even
multiplicity therefore yields exactly the same polynomial. Basis rows are still
independently sorted and duplicate basis terms rejected. Equation sizes, their
stable evaluation order, all certificate fields and evaluation counters remain
identical. This argument applies to duplicate packed masks with different
coefficients as well as canonical ANF input.

For M packed terms and E dense equations, repeated row sorting can cost
O(E M log M). Shared ordering reduces that component to O(M log M + E M),
using at most 4M bytes for indices. Already ordered input needs no index buffer.
Fresh coefficient data, row storage and root computations remain per query.
This changes decoding work; it does not change the asymptotic complexity of
Gröbner computation or the exponential truth-set verifier's 20-variable bound.
The separate larger-ring algebraic checker from round11 remains a distinct path.

## Complete-query results and limits

Both runs contain the same ten frozen planted controls and three arms in shuffled
order. The screen has 15 paired measurements plus warmup per control (480 verified
attempts). After its wide wall-time uncertainty, we fixed the confirmation at 31
pairs plus warmup (960 verified attempts). All 1,440 attempts verified, with
identical basis hashes, assignments and certificate contents across each group.
Each report embeds its exact source snapshot; the test file gained an additional
nonstandard-tail rejection control between snapshots and later gained random
systems with planted zeros. Executed numerical code stayed the same. The screen's final smaller controls overlapped our brief
final correctness run; confirmation ran without another test or build launched
by this task. Both runs and all individual samples are retained separately.

The table shows confirmation of `baseline / ordered` complete-query wall time on
the six 18-variable controls. Each ratio is the geometric mean of paired wall
ratios, not the ratio of the two marginal medians.

| Seed | Baseline median ms | Ordered median ms | Paired wall GM [bootstrap 95%] |
| --- | ---: | ---: | ---: |
| 101 | 103.660 | 95.090 | 1.197 [1.056, 1.350] |
| 102 | 86.638 | 73.306 | 1.074 [0.958, 1.195] |
| 103 | 71.865 | 58.494 | 1.106 [0.948, 1.272] |
| 104 | 46.780 | 46.160 | 1.078 [0.977, 1.196] |
| 105 | 52.213 | 45.380 | 1.192 [1.050, 1.346] |
| 106 | 47.680 | 41.223 | 1.109 [0.982, 1.248] |

Only two confirmation intervals lie wholly above one. The earlier screen has one
such 18-variable interval and one paired point estimate below one. Confirmation
CPU-time ratios are consistently 1.120–1.151 with intervals above one on these
six controls, but CPU time is a diagnostic, not a replacement for the wall-time
gate. There is no uniform complete-query win, another 2x, or default promotion.

The smaller controls remain mixed: confirmation ordered wall GMs are 0.867 for
n31/ell3, 1.007 for n31/ell4, 0.940 for n11/ell2 and 1.055 for n83/ell2; every
interval crosses one. Wide-field replay still dominates its control. `row-check`
alone also has mixed results; its full ablation is retained in `results/summary.json`.

The shared Apple M4 Pro has 14 logical CPUs and 48 GiB RAM, running Python 3.13.1.
One-minute load was 24.7–30.4 across the screen and 34.7–43.0 across confirmation.
Absolute timings therefore differ sharply from earlier rounds: do not compare
them as if they were paired measurements or multiply historical speedup ratios.
These observations do not establish performance on an idle or dedicated host.

The interval starts with a supplied target coordinate and includes fresh native
descent, packed solving, independent decoding/certification, original equation
and curve replay, and an additional untouched reference-ANF check. Exclusive
phase nanoseconds sum to complete query wall time. Library/layout construction
and fixture generation are separate setup. Per-query library-hash file reads
remain charged in all arms. Phase medians are marginal and must not be added.
Parent memory high water is recorded; per-query memory peak is unknown.

These planted component controls do not estimate natural relation yield or
recover logarithms. The original curve oracle reconstructs its reference point
from fixture points inside the charged replay interval. Candidate identity and
IC/rho online times remain null. The producer is evaluation plus
Buchberger–Möller interpolation, not an improved F4/F5 implementation. This is
neither a GPU result nor an F6 or asymptotic Gröbner breakthrough.

An initial launch stopped during a sandbox-denied CPU metadata query before
creating any fixtures or timed attempts. Its log is retained as
`results/metadata-setup-failure.log`; the unchanged benchmark was then allowed to
read host metadata. No measured attempt was discarded from either complete run.

## Validation and reproduction

Four test groups pass locally in 9.187 seconds. They cover 72 random systems
(half with an explicitly checked planted zero),
216 ordering/parity cases across all six optimized/UBSan builds, comparison with
the separate Python truth/staircase checker, unordered basis terms, duplicate
cancellation, empty and zero equations, the 20-variable and 4,096-equation bounds,
63/64/65 and 127/128 equation boundaries, malformed pointers/offsets/masks/high
coefficient bits, rejection codes 1–6, all certificate fields and counters,
concurrent alternating valid/changed inputs, and complete queries with curve
replay over GF(2^11), GF(2^31) and GF(2^83). The unchanged producer remains bounded
to 256 roots. The libraries do not impose a hard wall timeout.

From the repository root with Python >=3.10 and Clang or GCC:

```sh
python3 experiments/groebner-perf-20260924/round4/build.py
python3 experiments/groebner-perf-20260924/round14/build.py
python3 experiments/groebner-perf-20260924/round15/build.py
python3 -m unittest discover -s experiments/groebner-perf-20260924/round15 -p 'test_*.py' -v
python3 experiments/groebner-perf-20260924/round15/verify_evidence.py
python3 experiments/groebner-perf-20260924/round15/benchmark.py --repetitions 31 --output /tmp/ordered-new-run.json.gz
```

For a library call, import `query` from `ordered_query.py` and select
`arm='baseline'`, `'row-check'` or `'ordered'`. Input can be a dictionary or the
owned `PackedANF` returned by `NativeDescent.descend_packed`. Close query/descent
objects explicitly or use their context managers. There is no implicit compiler
invocation, backend fallback or default dispatch change.

CI repeats builds and correctness on Linux/GCC and macOS/Clang and audits the
frozen evidence. Inventories are integrity records, not external attestations.
The next practical targets are independent truth evaluation and native public-
point curve replay, followed by complete-query GPU verification experiments.
