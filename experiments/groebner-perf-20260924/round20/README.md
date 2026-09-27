# Complete one-target IC with the packed Boolean verifier

Round 20 connects the packed CPU query path to ordinary relation collection,
full-rank factor-base logarithms, recovery of one previously unseen public
target, and independent Python scalar replay. The comparison changes only the
certificate/equation path: the baseline uses round 15's ordered certificate and
Python original-equation replay; packed uses round 18's bit-sliced zeta
certificate and native direct packed replay. Both use the same producer,
descent, root ordering, relation policy and signed full-point replay.

This is a bounded experiment on **EC1N13Ckb1h0f132ba0b5e2**, field size 8192,
curve order 8012, subgroup order **2003 (11 bits)**. Its actual solver is Boolean
evaluation with Buchberger–Möller basis construction, so the candidate code is
`PDP3eval`. This is not an F4/F5 implementation or a new asymptotic algorithm.

| Prefix dimension | Boolean variables | Geometric points | Actual usable base B | Folded columns |
| --- | --- | --- | --- | --- |
| 3 | 9 | 11 | 8 | 4 |
| 6 | 18 | 63 | 60 | 29 |

Each base is compared with itself on frozen public points and resource limits.
The experiment does not claim that changing the base improves performance.
Both exact bases are retained in `experiments/fb-archive`; the archive rebuild
receipts are in `results/factor-base-audit.json`.

## Online interval and retained failures

`PreparedIC` receives no target or target secret during preparation. It collects
ordinary uniform nonzero `[k]G` queries, checks every certified root, verifies
signed point sums and exact factor-base membership, projects relations into
the subgroup, and stops at full column rank. It independently replays every
column logarithm. Each prepared object can consume exactly one public target.

The external fixture samples a nonzero public subgroup point, excluding all
preparation queries and their negatives, the generator, and known projected
base columns. The private fixture scalar is used only by the external audit.
The online clock starts before public-point validation and stops after Python
`[recovered_scalar]G == Q` replay. It charges every `Q+[a]G` attempt, including
unsatisfiable systems, rejected lifts, budget outcomes and errors. The five
exclusive phase costs sum exactly to that interval. Target-independent
preparation is recorded separately and is never amortized over targets.

The paired reference is the existing `ic-bench` three-set Floyd rho with
32 restarts and `20*floor(sqrt(r))+100` steps per restart. It receives the same
point and charges the same independent Python validation and final replay.
It is a declared reference, not a claim to the fastest possible rho code.

The shared receipt contract now supports `verified_online_wall`. All operation
counts, normalized operation ratios and amortization fields stay null in that
mode: the native components are not completely metered. Existing calibrated
operation receipts keep their previous requirements. Complete wall receipts
require same-point IC/rho scalar certificates and complete online accounting.

## Independent audit and local evidence

`audit.py` reconstructs the S4 descent using the separate Python `Pieces`
implementation and checks the complete reduced Boolean basis with independent
Python truth bitsets and staircase dimensions. It also checks full signed
curve witnesses, cofactor projection, a separate dense modular rank reduction,
every column log, deterministic query streams, the unseen-target condition,
final IC/rho scalars, phase accounting, source identities and selected native
binary hashes. Repeated proofs are cached only in this offline auditor.

The local tests include exhaustive relation-presence comparisons on all 2002
nonzero subgroup points for both arms: **4004 comparisons**, with 1946 proved
unsatisfiable and 56 verified decompositions per arm. Additional controls cover
corrupted receipts, basis roots, witnesses and column logs; unavailable full
rank; target budgets; identity relations; subgroup/field errors; and reuse of
a consumed context. Packed recovery is tested with dictionary conversion
disabled. Correctness traces cover both 9 and 18 Boolean variables.

Local timing was rejected at load 26.6069 on 14 logical CPUs before any timed
attempt. The separately labelled correctness traces contain observed durations
for accounting checks, **not qualified performance results**. The initial
smoke started before the native dependency build completed; that failed launch
and the successful rerun are both retained. `results/inventory.json` hashes all
retained evidence; `verify_evidence.py` checks tracking, hashes, final source
binding and the independent audit.

## Reproduce

Use Python 3.12 or 3.13, NumPy 2.4.0, a C compiler and Clang C++17:

```sh
python experiments/groebner-perf-20260924/round20/build.py
python -m unittest discover -s experiments/groebner-perf-20260924/round20 -p 'test_*.py' -v
python -m unittest discover -s experiments/ic-candidate-catalog -p 'test_*.py' -v
python experiments/groebner-perf-20260924/round20/measure.py --repetitions 31 --output /tmp/packed-ic.json.gz
python experiments/groebner-perf-20260924/round20/audit.py /tmp/packed-ic.json.gz
```

The benchmark refuses to overwrite receipts. Admission requires one-minute
load no greater than logical CPUs; initial, every paired-group start/end, and
final load must pass for a qualified comparison. Admission is necessary but
does not establish exclusive hardware. `--correctness-only` bypasses the wait
and permanently disqualifies its report from performance claims. The default
six workloads are six separate one-target studies (three frozen points per
base), each with fresh preparation per arm and repetition. They are not a
multi-target amortized workload. Order is randomized; one warmup is retained
and excluded from timing summaries. Paired bootstrap intervals describe
timing variation on each fixed point, not uncertainty across a population of
targets. Failures invalidate a speedup comparison and remain in the report.

The CI workflow builds optimized and UBSan libraries on Linux and macOS, runs
correctness and the independent audit, and attempts 31 paired repetitions per
public point after load admission. Artifacts retain the source snapshot,
compiler commands, binaries' hashes, runner metadata, all attempts and audits.

## Next work

Use the admitted complete-query phase breakdown to select the next optimization.
Compare useful root extraction, equation replay and basis-certificate work
under the same online gate. Keep CPU dispatch until a complete GPU query wins
including synchronization and replay. Larger algebraic certificates and
variable-separator/structured-operator hypotheses remain separate research
directions; this small evaluation experiment does not establish scaling or a
global performance ranking.
