# Sparse exact verification inside complete one-target IC

Round25 measures whether the independently checked sparse staircase proof from
round23 improves complete target recovery. Both arms retain the merged round21
first-usable target policy. The baseline uses the round18 packed evaluator and
dense proof; the candidate uses the same independent evaluator with round23's
bounded sparse proof and exact dense fallback. The checker is installed in each
workspace before reusable collection starts. No global factory is replaced.

Collection, rank construction, column logs, rerandomization, target witness
selection, direct equation evaluation, signed curve checks and final independent
Python scalar replay are unchanged. Only the independent checker differs. Its
allocation belongs to preparation; every target-dependent query, unsuccessful
attempt and fallback belongs to the online ledger. There is no target-answer
cache. A target context can be used once.

## Mathematical scope and identity

The controlled curve is `EC1N13Ckb1h0f132ba0b5e2`: field size 2^13, subgroup
order 2003 (**11 bits**). Prefix dimensions 3/6 contain 8/60 actual usable
factor-base points and 4/29 folded columns, giving 9/18 Boolean variables. These
are separate workload families, not a comparison between factor-base sizes.
The producer is evaluation/Buchberger–Möller (`PDP3eval`); this experiment does
not measure F4/F5 or establish asymptotic scaling.

Each candidate manifest binds all sources, exact field/curve/base, selected
checker, bounds, fallback policy, first-usable target rule and resource limits.
Per-run build receipts bind the selected native binaries, compiler and generated
proof source. The sparse proof requires exact ideal equality and independently
evaluated roots; its compact root/standard lists are bounded by 256 and its
divisibility budget is 65536. The budget-8 library is a test-only fallback control.

The same six public fixtures as round21 are retained: seeds 701/702/703 for
each base. A workload now explicitly records rho's walk partition, collision
policy, one worker, restart/iteration limits, zero distinguished-point storage,
absence of shared target state, RNG law and sources. Its new canonical identity
retains the prior workload ID. The audit independently reconstructs the exact
fixture, prior identity, exclusion set and all policy fields.

## Primary measurement

Each observation is one unseen public target, with a freshly prepared context
per candidate. IC and rho receive the same public point without its fixture
scalar. Timing starts before target validation and ends after independently
verified recovery. Reusable preparation and fixture construction are separate.
All target failures and fallback work remain charged; all result rows remain in
the journal. The five exclusive target phase costs sum to online wall time.
Rho performs one single-point Floyd walk and both native and independent Python
scalar replay; its policy receipt is assembled outside that interval.

The headline ratio is paired `rho_online / IC_online`, per public point and
candidate. The secondary engineering comparison is `packed_online /
sparse_online`. A comparison is qualified only when all attempts verify and
load admission holds at the initial sample, every group start/end and final
sample. The one-minute load must not exceed the logical CPU count. This gate
is necessary, not proof of an exclusive host. Repetition counts and 95% paired
bootstrap intervals are retained. One warmup is retained and excluded from
timing summaries. Arm and preparation order are randomized; reports never use
batch amortization. Unmetered operation counts remain null.

The hash-chained journal and no-overwrite behavior are retained from round21.
Partial, rejected and correctness-only runs cannot qualify as timing results.
Correctness-only traces use the separate seed 401. The offline auditor checks
the full journal against the aggregate, reconstructs original equations, checks
the exact basis independently in Python, verifies signed witnesses, projected
rows, rank/logs, target root prefix, scalar replay, receipts and exclusive costs.
Only this untimed auditor caches repeated proof checks.

## Reproduction

Use Python 3.12/3.13, NumPy 2.4.0 and the native compiler recorded by each build:

```sh
python experiments/groebner-perf-20260924/round20/build.py
python experiments/groebner-perf-20260924/round23/build.py
python -m unittest discover -s experiments/groebner-perf-20260924/round25 -p 'test_*.py' -v
python experiments/groebner-perf-20260924/round25/measure.py --repetitions 31 --output /tmp/sparse-ic.json.gz
python experiments/groebner-perf-20260924/round25/audit.py /tmp/sparse-ic.json.gz
python experiments/groebner-perf-20260924/round25/verify_evidence.py
```

The 17 test groups include parity with the actual merged pipeline, all 2002
nonzero toy-subgroup points at 9 variables, 32 ordinary 18-variable queries,
complete recovery, UBSan, forced fallback, corrupted certificates, producer
budgets/errors, one-use contexts, installation cleanup and concurrent workspace
isolation. Additional controls reject altered certificate backends, native
hashes, generated proof sources, rho policy/targets, root prefixes, duplicated
runs and omitted time. Admission and journal integrity have separate controls.

CI builds native code independently on Linux and macOS, runs the new controls,
frozen first-usable pipeline regressions and candidate-contract tests, audits
both complete correctness workloads and verifies retained source-bound evidence.
PR runs then attempt 31 paired measurements per public point after at most 240
seconds of admission waiting, preserving zero-attempt rejection receipts. Host,
compiler, binaries, logs, reports and audits are uploaded on every outcome.

The sparse arm remains explicit. This experiment alone does not change default
dispatch, claim a rho advantage, establish larger-subgroup behavior, or resolve
the verifier's current 20-variable enumeration limit.

## Local complete-recovery result

The admitted physical Apple M4 Pro run (14 logical CPUs, macOS 26.6, Python
3.13.1, NumPy 2.4.0) retained 31 paired observations and one warmup per public
point. All 192 recoveries per arm and 192 same-point rho runs verified. The
offline audit reconstructed 274 unique exact basis proofs and 42 signed curve
witnesses. These counts include the six warmups; timing summaries exclude them.

Each row below is one target on the exact curve and base above. The final
three rows use sparse candidate `IC1N13Ckb1fb60PDP3evalRCsampleLAgaussTDpdpISO0h7a2864c1545a`;
the first three use `IC1N13Ckb1fb8PDP3evalRCsampleLAgaussTDpdpISO0h73c01363be38`.
Complete manifests, both candidate IDs, target coordinates and run identities
are in `results/paired-local.json.gz`; every result is independently verified.
The primary same-point rho/IC ratio is below one in every row, so rho wins.

| Workload | Actual base | Packed IC ms | Sparse IC ms | Same-point rho ms | Paired rho/sparse IC | Paired packed/sparse IC (95% interval) |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `331da6ce9396` | 8 | 5.310 | 5.321 | 1.257 | 0.244 | 1.000 [0.960, 1.041] |
| `58597fefde7d` | 8 | 11.810 | 12.065 | 1.469 | 0.125 | 0.990 [0.971, 1.007] |
| `9e576df7a8f8` | 8 | 12.439 | 12.568 | 1.251 | 0.099 | 0.984 [0.968, 1.001] |
| `268df6a9d7a0` | 60 | 2.463 | 2.335 | 1.253 | 0.541 | 1.064 [1.038, 1.095] |
| `62739dbc9f6d` | 60 | 2.724 | 2.574 | 1.429 | 0.560 | 1.051 [1.035, 1.067] |
| `9f000edc97a2` | 60 | 2.913 | 2.661 | 1.283 | 0.479 | 1.080 [1.061, 1.100] |

Online times are medians; ratios are paired geometric means and need not equal
the ratio of medians. Full rho/IC confidence intervals and exclusive phase costs
are in `results/paired-local-audit.json`. Each 18-variable target shows a
5–8% complete-recovery improvement in this run; the 9-variable intervals all
include one. This is one admitted host run, pending independent CI replication.
Default dispatch remains unchanged.
