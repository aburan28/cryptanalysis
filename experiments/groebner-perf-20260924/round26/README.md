# Independent scalar replay with matched rho controls

Round26 replaces exponentiation-based inversion in the independent Python field
checker with polynomial extended Euclid. The native producer, packed ANF path,
exact basis checker, signed native curve witnesses, point-addition formulas and
scalar double-and-add algorithm remain unchanged. The reference arithmetic is
retained as a separate `power` arm and as the untimed mathematical audit oracle.
The `euclid` arm is explicit; this experiment does not change global dispatch.

This is the standard polynomial extended Euclidean method, specialized to
binary coefficients, rather than a new cryptanalytic algorithm. See
[Handbook of Applied Cryptography, section 2.6.2, algorithm 2.221](https://cacr.uwaterloo.ca/hac/about/chap2.pdf).
The code records its loop invariant and termination argument. It checks
canonical input integers, rejects zero and terminates on a nonunit even if an
already-validated field object is subsequently corrupted. Only `inv` changes;
reference multiplication, squaring and curve addition retain their old code.

## Installation and independence

The frozen complete-IC constructor installs its oracle inside the charged setup
ledger, before preparation. A per-instance property substitutes the independent
field only for the selected Euclid arm. No global method or factory is changed,
and concurrently prepared contexts can use different arithmetic. The new field
reads no producer state, target answer, relation log or native inverse. It has
no target-answer cache. Each IC target context remains single-use.

Both public-point subgroup validation and final scalar replay use the selected
oracle. Reusable projection and column-log checks use it as well, with their
cost charged to preparation. Inversion is never moved out of a target-dependent
check. Receipt metadata is constructed after the complete verification interval,
as in round25. The offline auditor retains exponentiation-based arithmetic and
independently checks exact bases, curve witnesses, projected rows, rank/logs,
root prefixes and every recovered scalar.

## Fair complete-recovery comparison

Each workload has four single-point executions: `power`, `euclid`, `rho-power`
and `rho-euclid`. Rho's underlying native walk is unchanged. Each IC candidate
is paired with the rho run using **the same independent arithmetic**, public
point, one-worker policy and resource limits. The receipt writer and auditor
reject mixed pairings. Both IC arms get fresh preparation per repetition; neither
receives the fixture scalar. Execution and preparation order are randomized.

The fixed basis checker is `packed` at 9 variables and `sparse` at 18 variables,
identical between replay arms for each workload. This is a declared benchmark
configuration, not an automatic production routing policy. The exact curve is
`EC1N13Ckb1h0f132ba0b5e2`, field size 2^13 and subgroup order 2003 (11 bits).
Actual bases of 8/60 points have 4/29 folded columns. The solver is
evaluation/Buchberger–Möller (`PDP3eval`), not an F4/F5 comparison. The same six
public fixtures as round25 are retained under new source/policy identities;
the prior workload identity is also retained and reconstructed by the auditor.

The primary metric is one unseen target's online wall time from first public
validation through independently verified recovery, paired with its matching
rho reference. All attempts, failures and dense certificate fallback are charged.
Preparation and fixture generation are separate. Five exclusive target phase
costs sum to online time. Unmetered operation counts remain null. Repetition
count, all failures, source/native/host receipts and uncertainty remain recorded.
The secondary engineering ratios are power/Euclid complete IC time and
power/Euclid complete rho time. These can differ substantially because replay
occupies different fractions of the two algorithms.

The default experiment has 31 measured repetitions when invoked below and one
retained warmup per public point. No target batching or shared-table amortization
enters the headline metric. Load admission requires the initial, every group
start/end and final one-minute load to be no greater than the logical CPU count.
Correctness-only runs use seed 401 and are permanently ineligible for speed claims.
Rejected and partial runs remain evidence; existing files are not overwritten.

## Validation and reproduction

The 20 test groups include 10,786 exhaustive nonzero inverse comparisons across
small fields, including the entire 13-bit field; 655 randomized/boundary inverse
controls through 128 bits; all 2,003 toy-subgroup scalars and exceptional curve
cases; 24 complete IC/rho parity controls against the actual merged pipeline;
invalid points, corrupted scalar replay, parallel workspace isolation, failed
setup and single-use enforcement. Audit mutations cover mismatched rho/checker
pairings, arithmetic identity, basis/native/source records, root prefixes and
omitted time. Admission and journal integrity are tested separately. Larger-field
inverse controls do not establish complete IC performance at those sizes.

Use Python 3.12/3.13, NumPy 2.4.0 and the native compiler recorded in each report:

```sh
python experiments/groebner-perf-20260924/round20/build.py
python experiments/groebner-perf-20260924/round23/build.py
python -m unittest discover -s experiments/groebner-perf-20260924/round26 -p 'test_*.py' -v
python experiments/groebner-perf-20260924/round26/replay_measure.py --repetitions 31 --output /tmp/replay.json.gz
python experiments/groebner-perf-20260924/round26/replay_audit.py /tmp/replay.json.gz
python experiments/groebner-perf-20260924/round26/verify_evidence.py
```

CI independently rebuilds native dependencies on Linux and macOS, runs these
controls and the merged round25 regressions, checks the candidate contract,
audits both full correctness workloads and verifies retained source-bound
evidence. PR jobs attempt the paired measurements after at most 240 seconds of
load admission waiting and retain every outcome. An IC advantage over rho,
asymptotic improvement or global performance ranking is not presumed.
