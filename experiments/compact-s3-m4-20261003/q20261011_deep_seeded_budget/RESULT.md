# Q1438: deeper seeded budgets expose a one-sided search bottleneck

At a fixed 30-second cap, the `seededpos` decision order checked **90 N53**
and **128 N83** middle states; every one was on middle row 5. The
`seededspread` order checked only two row-4 states in each field. The result
pinpoints the next solver step: assign and test both middle rows in the same
search. More one-sided coverage is not yet a useful relation-yield measure.

The same frozen ordinary public point and factor-base construction as Q1437
were used in each field. N53 is `EC1N53Ckb1hf77aab617904`, with actual
B=24,062 and folded K=227. N83 is `EC1N83Ckb1h876c2921cb64`, with
actual B=30,977,592 and folded K=186,612. Their enumerated-set digests are
`05b75578ee58866bc8e5d3199cc77f441fa8649ccbaf88c089e998a00ea435e5`
and `56c951ad78cc4036d3e8ff70bcb9d7feccacc6c763220b285def056cba30afb8`.
Both use `isogeny: "none"`. This is `Q1438`, a PDP-stage proposal with
`candidate_id: null` and `run_id: null`.

## Frozen allocation and results

The Q1437 sixteen-seed screen selected seed 2 at N53 and seed 8 at N83
before these timings. For each field, one fresh `seededpos` and one fresh
`seededspread` solver process used the Q1437 executable, `satpivot` S3 roots,
`selector` early target support, `eager` rationality checks, a 128-state
support cap, 5,000 conflicts, and 30 seconds. No clauses were shared.

| Field / decision order | Status / limit reached | Conflicts | Checked row 4 / row 5 states | Final-link checks | Counted field API entries |
| --- | --- | ---: | ---: | ---: | ---: |
| N53 `seededpos` seed 2 | `BOUNDED_UNKNOWN`; wall | 56 | 0 / 90 | 0 | 4,320,272 |
| N53 `seededspread` seed 2 | `BOUNDED_UNKNOWN`; conflicts | 5,000 | 2 / 0 | 0 | 751,751 |
| N83 `seededpos` seed 8 | `BOUNDED_UNKNOWN`; wall | 61 | 0 / 128 | 1,645 | 383,928 |
| N83 `seededspread` seed 8 | `BOUNDED_UNKNOWN`; wall | 3,689 | 2 / 0 | 8 | 590,684 |

The N83 `seededpos` run hit its 128-state support cap and recorded 823
additional skipped middle-state checks. The N53 `seededpos` run spent 30.11
solver seconds on 90 checked row-5 states, with no completed final-link
check. Thus an early-support count alone is insufficient for choosing the
next decision order. The per-run method vectors, status, process and solver
times, caps, raw log hashes, and exact inputs are in `measurements.json`.

Because these seeds were selected from the Q1437 screen on the **same**
point, the one-target ledger includes both rounds:

| Field | Q1437 screen entries | Q1438 additional entries | Cumulative charged entries | Distinct checked states after both rounds |
| --- | ---: | ---: | ---: | ---: |
| N53 | 4,881,904 | 5,072,023 | 9,953,927 (\(2^{23.25}\)) | 146; 84 new in Q1438 |
| N83 | 1,804,072 | 974,612 | 2,778,684 (\(2^{21.41}\)) | 206; 105 new in Q1438 |

All four additional ordinary attempts have status `BOUNDED_UNKNOWN`.
Successful-query cost and relation yield are therefore still unmeasured.
The N131 necessary ceiling of less than \(2^{33.36}\) abstract work units
per ordinary query under a \(2^{61}\) total cap uses a different work unit.
The fully charged N131 \(2^x\) projection and challenge gap remain null.

`validate.py` rechecks the source, runner, binary, prior-campaign and log
hashes; all caps, statuses, operation sums, state unions and costs; and 32
independent rejected-leaf trace decisions. It records `PASS` and the
row-4/row-5 split in `validation.json`. Q1437's locked N53/N83 S3 controls
also recorded `PASS` with the same executable.

## Next experiment

Modify the decision callback to promote assignment of the *unassigned*
middle pair after one middle is fixed. Measure the count and work of complete
row-4/row-5 final-link checks on the same frozen N53 and N83 public points.
Retain all Q1437 and Q1438 screening costs in a cumulative one-target ledger
when selecting the new policy. A complete relation must pass independent
curve-point and factor-base replay before its cost can be used for a
degree-131 successful-query projection.

## Reproduction

After generating the frozen Q1430 inputs and Q1432 targets and building
Q1437's executable:

```sh
python3 experiments/compact-s3-m4-20261003/q20261011_deep_seeded_budget/run.py --binary /private/tmp/q1437_insearch
python3 experiments/compact-s3-m4-20261003/q20261011_deep_seeded_budget/validate.py --binary /private/tmp/q1437_insearch
```
