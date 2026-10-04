# Prepared cost-aware τ scalar multiplication: C integration

This branch is stacked on PR #250. It imports the existing local prime-field
`j=0` τ implementation whose pre-import `src/ec_tau.c` SHA-256 is
`128003abecae34fd715e7e5c82020ac79fd8ef2b4a42d1ee5f1be03c8bc410c3`.
The import is scoped to scalar arithmetic: no rho walk or dispatch is changed.
It adds an opt-in prepared evaluator that searches the same 25 representatives
as the baseline, scores each exact width-4 schedule with the frozen
`10 triple + 16 mixed add + 1 nontrivial unit rotation` model, and evaluates
the selected digits with the same precomputed points and tripling formula.
The selected digits are reused directly; there is no 26th recoding.

## Correctness result

The C curve test compares ordinary `ca_group_mul`, prepared L1 τ, and
prepared cost-aware τ on 999 public-scalar cases: two registered j=0
subgroups (each on two public points), a complete scalar sweep of the
order-103 toy subgroup, and a 56-bit subgroup over `p=2^61−1`.
Boundary cases include zero, one, `r−1`, `r`, and `UINT64_MAX`.
The modified `test_curve` passed all 6,150 checks. The build used Apple clang
17 with `CA_WERROR=ON`. The exact source and command receipt is
[integration-check.json](integration-check.json), with
[test-curve output](integration-test-curve.log).

The full local suite passed 14 of 15 tests. `coord` failed at its local
socket `bind()` call; an independent Python socket bind on `127.0.0.1`
returned `PermissionError` (`errno=1`) in this sandbox. Its entire failing
output is retained in [integration-ctest.log](integration-ctest.log). The
full-suite result remains **incomplete**, pending CI on an environment that
permits localhost binding. No wall-time comparison was performed here.

## Frozen speed experiment to run after this protocol is published

The first target workload is a prepared rho-setup scalar panel, because the
same base or target point is multiplied by many public jump/restart scalars.
Freeze two exact j=0 curves: `glv-j0-32` with
`p=4294967377, a=0, b=15, r=23729779`, and the 56-bit subgroup
`p=2305843009213693951, a=0, b=7, r=53624256071278747`. For each curve,
take `ca_group_find_generator(..., seed=1)` and its multiple `37P` as the
two input points. Generate 4,096 scalar inputs per point with standard
SplitMix64: initial state is `20261004 XOR (curve_index << 32) XOR
point_index`, with indices 0 and 1 in the order written above; each draw
increments the state by `0x9e3779b97f4a7c15`, then applies the usual xor-shift
30/multiply `0xbf58476d1ce4e5b9`, xor-shift 27/multiply
`0x94d049bb133111eb`, and xor-shift 31. Reduce each output modulo `r` and
preserve generation order and any duplicates. Both arms receive identical
encoded points and scalar lists.

Prepare the nine seed and nine τ-seed points once per input point **outside**
the measured interval. Start the online clock immediately before the first
scalar's representative selection and stop after the last output point is
produced. Include all recoding, unit rotations, triplings, additions, and
conversions in the interval. Replay every output with ordinary `ca_group_mul`
and compute an ordered output digest outside the interval, recording replay
time separately. The two arms must report the same frozen input digest and
the same independently checked output digest. Also record preparation time,
total triples and additions, output failures, compiler and binary hashes.

Run the paired panel on the isolated benchmark service with at least five
paired repetitions per curve/point arm and alternating AB/BA order. Preserve
all raw repetitions and any failed preflight or noise gate. The headline is
the paired **prepared-panel** wall-time ratio, clearly labeled as such; a
single-call cold result, if added, is a separate workload that includes all
preparation. A faster modeled chain or an ordinary-host timing ratio does not
promote a CPU speedup claim. The `nohz_full`, exclusive partition, NUMA,
frequency, IRQ, and correctness receipt gates in
[ISOLATED_BENCHMARKS.md](../../docs/ISOLATED_BENCHMARKS.md) apply.
