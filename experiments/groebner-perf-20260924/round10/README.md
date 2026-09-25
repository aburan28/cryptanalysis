# Complete-query GPU workspace experiment

This opt-in experiment connects the qualified round-seven Metal RREF kernel
to the existing bounded Boolean hybrid through a packed native library.
Every query includes independent basis certification and equation/curve
replay. Production dispatch remains unchanged; `HybridQuery` defaults to CPU.

The screen does **not** establish a stable GPU crossover. On this heavily
loaded shared M4 Pro, GPU reduction helped some 12-variable hybrid controls,
but evaluation/interpolation was substantially faster. Six- and nine-variable
queries lost on the GPU. Pre-encoded indirect commands did not produce a
reliable improvement over direct command encoding.

## What is reused and what is charged

Prepare the ring, monomial order, descent contraction plan, pipeline states,
scratch buffers and bounded command plans before receiving the target. The
8192-row capacity is selected in advance; it is not inferred from that target's
matrix. Actual row count selects the local/global panel plan and command
prefix during the charged query. Direct submission uses the actual row count
for its grid; the indirect plan dispatches its fixed capacity with shader bounds
checks. Thus their comparison measures the complete submission policies, not
encoding overhead alone.

Every invocation resets all numerical GPU buffers. The hybrid copies an
immutable ring template into a fresh engine: no rewrite rules, syzygies,
coefficients, pivots, roots, or bases cross query boundaries. Python protects
workspace lifetime; native calls serialize the process-global M4RI allocator.
This is a single-query latency experiment, not concurrent throughput.

The measured interval starts with a public target coordinate, then includes
fresh descent, packed transport, bounded signature seeding, Macaulay generation,
RREF, scalar completion, independent truth/staircase certification, original
equation evaluation, curve replay, and evaluation against the untouched reference
ANF. Ring-only setup and fixture construction are recorded separately. No
logarithm is recovered: `candidate_id`, `IC_online_ms`, and `rho_online_ms`
remain null. Planted controls do not estimate natural relation yield.

The solver handles 1–12 Boolean variables and 1–64 equations, with at most
8192 prepared matrix rows. Exceeding capacity returns an inconclusive result
and preserves the attempt's elapsed time; there is no hidden CPU fallback.
There is no hard per-query timeout in this in-process interface. The inherited
curve-replay path requires at most 256 certified roots; larger certified ideals
are supported by `compute()` but not by `solve()`.

This is bounded signature seeding followed by ordinary matrix reduction and
complete scalar closure. It is not a signature-safe GPU F5 implementation.

## Retained results

Fifteen frozen controls (6, 9 and 12 variables; seeds 1–5) each have one retained
warmup and 15 randomized, paired repetitions across four arms: **960 verified
query executions**, 900 excluding warmups. Every arm has the same certified
reduced basis hash and recovered decomposition assignment for its input.

Illustrative 12-variable complete-query wall medians, in milliseconds:

| Seed | CPU hybrid | GPU direct | GPU indirect | Evaluation/interpolation |
| --- | ---: | ---: | ---: | ---: |
| 1 | 316.152 | 232.437 | 267.070 | 38.581 |
| 2 | 227.686 | 157.560 | 155.842 | 8.539 |
| 3 | 120.455 | 92.989 | 120.380 | 3.314 |
| 4 | 65.802 | 91.670 | 69.648 | 3.810 |
| 5 | 345.431 | 157.081 | 156.855 | 5.907 |

For seed 1, paired CPU/direct-GPU geometric mean speedup is 1.407 with a
95% paired-bootstrap interval of [1.123, 1.791]. Seed 4 is 0.889
[0.652, 1.226]. These are exploratory per-cell estimates without a
multiple-comparison correction. Load average rose from about 34 to 47 on a
14-logical-CPU host. Process CPU time, full wall time, device time, setup, all
rows and warmups are retained. Do not use these load-sensitive numbers to
promote GPU dispatch or claim a repeatable 2× improvement. Bootstrap intervals
describe this run's samples, not uncertainty over machines or input families.

`audit.py` recomputes all 15 cells, paired ratios and intervals. The gzip receipt
retains the full original JSON; `results/inventory.json` pins evidence and
qualification source bytes. Binary hashes identify local builds, which are
rebuilt and tested elsewhere rather than claimed reproducible byte for byte.

Validation:

- 942 exact M4RI/Metal rank and RREF comparisons, including word/panel boundaries,
  repeated zero and random matrices, local/global panel transitions, capacity
  rejection, and 32 calls sharing a workspace across four threads.
- 345 CPU/direct-GPU/indirect-GPU basis checks against evaluation/interpolation;
  randomized small rings also pass the independent Python certificate.
- Malformed masks/coefficients, closed workspaces, capacity failure followed by
  successful reuse, and 32 threaded query calls are checked.
- CI runs the CPU query tests on Linux and macOS, compiles the Metal host on
  macOS, and audits the retained local GPU receipts. CI does not claim Metal
  execution or GPU performance measurements.

The earlier `workspace-validation.json` is a development smoke receipt; the
acceptance receipt is `workspace-validation-final.json`. Its test prepares the
independent M4RI answers serially before starting concurrent Metal calls.

## Reproduce

With clang++, Python and M4RI available, from the repository root:

```sh
python3 experiments/groebner-perf-20260924/round10/build.py --m4ri-prefix /path/to/m4ri
python3 experiments/groebner-perf-20260924/round10/test_query.py --gpu
experiments/groebner-perf-20260924/round10/build/test-workspace experiments/groebner-perf-20260924/round7/local_panel.metal
python3 experiments/groebner-perf-20260924/round10/benchmark.py --output /tmp/new-query-comparison.json
python3 experiments/groebner-perf-20260924/round10/audit.py
```

On Linux use `build.py --cpu-only` with pkg-config M4RI, then omit `--gpu`.
Ubuntu dependencies are `clang libm4ri-dev libpng-dev pkg-config`; its M4RI
pkg-config metadata requires libpng's development metadata as well.
The audit always checks the retained run, independently of a newly generated
benchmark output. Do not overwrite historical evidence to refresh a benchmark.

## Next experiments

1. Repeat the complete-query comparison under controlled host load before
   estimating a GPU crossover. Keep evaluation/interpolation in the comparison.
2. Measure adaptive pre-encoded capacity buckets and compact active columns on
   genuinely larger matrices. Any target-dependent compression/permutation and
   expansion belongs in the query interval; require exact rank/basis agreement.
3. Prioritize non-enumerative proof production and certificate checking on
   larger-variable systems, where the small-ring evaluation baseline no longer
   applies. Track certificate size and peak memory as well as solve time.
4. For structural algorithm proposals, test symbolic reuse only when its
   target independence can be proved. A shared support graph does not prove
   shared numerical pivots. Keep separator counterexamples and failed cases.
5. A full IC claim still requires one unseen public target through independently
   verified logarithm recovery, with all target-dependent failures charged and
   a paired rho measurement on the same point/resources.

Metal indirect command ordering uses Apple's
[indirect-command barrier API](https://developer.apple.com/documentation/metal/mtlindirectcomputecommand/setbarrier()).
Indirect buffer resources are explicitly declared to the command encoder.
No new asymptotic algorithm or globally fastest implementation is claimed.
