# Q1428: exact outer roots halve the anchored SAT formula again

Q1428 computes the first-pair and outer S3 roots with exact field
arithmetic. SAT then handles one fixed-output S3 link between two
normal-basis-weight-bounded leaves. On the matched N53 and N83 inputs,
the formula has exactly half Q1427's AND gates and XOR rows, and roughly
half its variables and CNF clauses. The known right pair passes the
pinned control at both degrees and its four-point relation replays on
the exact base. Six measured cells with the right pair free stopped as
`BOUNDED_UNKNOWN` under the frozen 90-second per-anchor cap.

## Frozen inputs and measured stage work

The proposal is `Q1428`, with `candidate_id: null`, `run_id: null`, and
`isogeny: "none"` (`ISO0`). N53 uses
`EC1N53Ckb1hf77aab617904`, Q1301 W≤3, B=24,062 exact usable
subgroup points, K=227 signed-Frobenius columns, and ordinary workload
`74f2979b3e68`. N83 uses `EC1N83Ckb1h876c2921cb64`, Q1325 W≤5,
B=30,977,592, K=186,612, and workload `bab50a1e5f66`. The curve,
base, source, binary, input, anchor, lift, and limit digests are in
[`freeze.json`](freeze.json), committed before the measured calls.

| Degree and input | Target PDP wall s | SAT calls | Exact conflicts | Propagations | Root branches attempted / available | Status |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| N53 known-solution control, right leaves free | 90.645 | 1 | 66,426 | 57,964,577 | 1 / 4 | `BOUNDED_UNKNOWN` |
| N53 ordinary anchor 0 | 90.036 | 1 | 88,007 | 75,373,341 | 1 / 8 | `BOUNDED_UNKNOWN` |
| N53 ordinary anchor 1 | 90.051 | 2 | 178,741 | 146,187,195 | 2 / 8 | `BOUNDED_UNKNOWN` |
| N83 known-solution control, right leaves free | 90.252 | 2 | 57,796 | 73,488,310 | 2 / 4 | `BOUNDED_UNKNOWN` |
| N83 ordinary anchor 0 | 90.135 | 2 | 66,736 | 103,099,986 | 2 / 16 | `BOUNDED_UNKNOWN` |
| N83 ordinary anchor 1 | 90.087 | 2 | 68,641 | 98,273,610 | 2 / 16 | `BOUNDED_UNKNOWN` |

Each ordinary anchor has two first-pair roots. The frozen schedule has
two of 428 N53 public-target lifts and all four N83 lifts, yielding
eight and sixteen exact outer-root branches respectively. The wall
cap stopped each ordinary cell after one or two SAT calls; the later
branches were not searched. The per-call configured limits were
100,000 conflicts and 25 CPU seconds. The native counter shim records
the exact last-call conflicts, propagations, and decisions; the
CryptoMiniSat return code does not identify which per-call limit fired.
The root oracle evaluated every scheduled branch before SAT: four
outer calls per N53 ordinary anchor and eight per N83 anchor. N53/N83
outer calls used 13 field-multiplication API calls and two inversion
API calls each; all field API counters are in the receipts. Peak process
RSS was 202–572 MiB under the declared 1,536-MiB ceiling. Exclusive
selection, root join, formula build/load, SAT, relation check, and
overhead clocks sum to each target-dependent PDP wall interval. CPU
wall-time ratios are exploratory without a host isolation receipt.

The formula reduction is exact: N53 has 9,111 variables, 26,006 CNF
clauses, 265 XOR rows, and 8,427 AND gates; N83 has 22,069 variables,
63,798 clauses, 415 XOR rows, and 20,667 AND gates. Q1427's matched
one-external-link formulas have 18,275/44,221 variables,
52,171/127,845 clauses, 530/830 XOR rows, and 16,854/41,334 AND
gates at N53/N83. Formula size has improved, while the recorded free
right-pair attempts remain censored before a SAT model. Conflict
counts from different branches and contended host runs are stage
diagnostics, not matched cost per relation.

## Known-solution control and complete-work ledger

[`test_right_pair.py`](test_right_pair.py) independently checked the
expected right-pair output against both exact-root joins, pinned the
two known right leaves only for that control, and solved the fixed
output formula in one SAT call with zero conflicts at both degrees.
The resulting N53 and N83 four-point relations passed exact curve,
subgroup, factor-base, distinct-column, and public-target checks. The
measured control rows above leave those leaves free and traverse root
branches in their frozen deterministic order; their first SAT branches
did not reach a model within the cap. [`verify.py`](verify.py) replayed
all six measured source-bound receipts, root joins, input IDs, formulas,
native counters, phase sums, and traces.

Q1428's N131 complete cold and one-target-online work exponents are
`null`. The ordinary cells have not supplied a natural relation yield,
cost per novel rank row, final matrix cost, target descent, or scalar
replay. Fitting an N131 relation-solve cost from these capped calls
would turn censored observations into completed solves. For comparison,
the separate [Q1422 explicit-index model](https://github.com/aburan28/cryptanalysis/pull/625)
has an exact-base floor of `2^88.356` logical actions, 27.356 bits
above `2^61`, and a relaxed global floor of `2^78.552` actions, 17.552
bits above. Those floors apply to an indexed-pair family, not to this
SAT/root method. The exact [N53 matched pair-table run](../compact-s3-m4-20261003/runs/n53_ordinary_matched_pair_table.json)
found a verified relation after 671,218 logical pair samples on the
same base and public target; pair samples and SAT conflicts are
different accounting units.

The next measured solver gate is the satisfiable fixed-output right-pair
control with its two leaves free and the known right output selected
first, followed by frozen ordinary output branches. That isolates the
cost of finding a right-pair witness from the cost of proving unrelated
outputs unproductive. A useful subsequent search should vary output
branch ordering, solver conflict/time caps, and partial pair indexing
under the same target and charge every unsuccessful branch. Promotion
to an N131 `2^x` estimate requires ordinary verified relations and
novel-rank measurements in a common work unit.
