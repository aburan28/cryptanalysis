# Q1427: early pair roots expose the remaining SAT search cost

Q1427 computes the first leaf pair's exact S3 roots before SAT and searches
the remaining two leaves with those roots as incremental assumptions. A
native counter shim records exact CryptoMiniSat conflicts, propagations,
and decisions for every call. Four ordinary anchor pairs were selected
deterministically from the exact N53 and N83 bases; each pair has two
distinct quotient columns and two exact S3 roots. The two known-solution
controls and four ordinary anchor runs all returned `BOUNDED_UNKNOWN`
before a first SAT model under the frozen caps.

The anchored split therefore reaches the root oracle before search, but
the remaining two-leaf/right-pair and outer S3 SAT system still consumes
tens of thousands of conflicts per branch. The next structural step is
to solve the *outer* S3 equation by its exact roots too, leaving only a
fixed-output right-pair decomposition in SAT.

## Exact input and measured work

Q1427 is an `ISO0` proposal with null candidate and run IDs. N53 uses
`EC1N53Ckb1hf77aab617904`, Q1301 W≤3, B=24,062 exact subgroup-usable
points and K=227 signed-Frobenius columns. N83 uses
`EC1N83Ckb1h876c2921cb64`, Q1325 W≤5, B=30,977,592 and K=186,612.
The ordinary workload IDs are `74f2979b3e68` and `bab50a1e5f66`.
Curve/base digests, source and library hashes, exact anchor coordinates,
roots, and target lifts are in [`freeze.json`](freeze.json).

| Degree, input | PDP wall s | SAT calls | Exact conflicts | Propagations | Root branches/lifts attempted | Result |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| N53 known-solution control | 58.992 | 2 | 200,003 | 109,484,028 | both roots; known lift | `BOUNDED_UNKNOWN` |
| N53 ordinary anchor 0 | 90.028 | 3 | 268,812 | 181,290,585 | both roots at lift 112; first root at 417 | `BOUNDED_UNKNOWN` |
| N53 ordinary anchor 1 | 90.024 | 4 | 300,384 | 194,361,554 | both roots at lifts 112 and 417 | `BOUNDED_UNKNOWN` |
| N83 known-solution control | 63.515 | 2 | 70,942 | 159,526,892 | both roots; known lift | `BOUNDED_UNKNOWN` |
| N83 ordinary anchor 0 | 90.225 | 3 | 69,751 | 158,347,388 | both roots at lift 0; first root at 1 | `BOUNDED_UNKNOWN` |
| N83 ordinary anchor 1 | 90.361 | 2 | 54,782 | 128,190,846 | both roots at lift 0 | `BOUNDED_UNKNOWN` |

The per-anchor budget was 90 target-dependent wall seconds, 17 SAT calls,
and 16 rejected complete models; per-call limits were 100,000 conflicts
and 25 CPU seconds. N53 calls often stopped near the configured conflict
count while N83 stopped below it; the solver API does not identify which
limit fired. No
complete SAT model was rejected or accepted. Ordinary anchor selection
took 3–7 candidate masks and 0.005–0.070 seconds; its rationality,
subgroup, exact-base, and root checks are recorded in each receipt. The
source-bound process peaks ranged from 475 MiB to 1,320 MiB, below the
1,536-MiB declared ceiling. Exclusive formula build, solver load, SAT,
selection, relation check, and overhead clocks sum to each PDP wall
total. CPU wall times are exploratory without host isolation.

The frozen schedule allowed N53 lift indices 112 and 417 and all four
N83 lifts for each ordinary anchor. The 90-second cap stopped N83 before
the later lifts. These are bounded **anchor attempts**, not complete
ordinary one-target queries. Their relation rate and cost per novel rank
row remain unknown.

## Matched pair-table comparison and the \(2^{61}\) ledger

The archived [N53 matched pair-table run](../compact-s3-m4-20261003/runs/n53_ordinary_matched_pair_table.json)
uses this exact base and public target and found one verified relation
after 500,000 table samples and 171,218 query samples: 671,218 logical
pair samples in total. Its base enumeration, table construction, and
target-query sampling took 32.78, 41.69, and 22.34 seconds in its
source-bound run. Pair samples and SAT conflicts are different units;
the current anchored cells do not supply a cost per relation to divide
against that comparator. The matched N83 pair sampler recorded 20,000
table and 20,000 query samples without a quotient-key hit under its
declared small-sample scope.

Q1427's N131 complete cold and one-target-online `2^x` fields remain
null. Neither a natural relation probability nor rank novelty, final
matrix cost, target descent, and replay have been measured for this
method. For the separate fixed explicit-index family,
[Q1422](https://github.com/aburan28/cryptanalysis/pull/625) gives an
exact-base floor of `2^88.356` logical actions (27.356 bits above
`2^61`) and a relaxed global floor of `2^78.552` actions (17.552 bits
above). Those action floors do not bound this anchored SAT solver.

## Verification and next solver gate

[`test_anchor.py`](test_anchor.py) checked all 35 three-of-seven masks,
two assumption branches with exact counters, and deterministic replay of
all four ordinary anchor choices. [`verify.py`](verify.py) checked all six
source-bound receipts, traces, exact roots, formula sizes, counters,
phase sums, and input IDs; its output is [`verification.json`](verification.json).
The small C++ shim and its archived binary are hash-bound to the measured
CryptoMiniSat library. The host-specific build command is
[`build_shim.sh`](build_shim.sh).

Next, compute exact roots of `S3(u_left, x_target, u_right)=0` for each
anchored left root and target lift. Fix `u_right` to each returned value
and run a single right-pair S3 constraint with its two leaves variable.
This removes the outer link from SAT while retaining a complete
four-summand search over charged anchors and lifts. Gate it on the
N53/N83 known-solution controls, then the same ordinary target/base
pairs. Count every root branch and failed solve before any N131 fit.
