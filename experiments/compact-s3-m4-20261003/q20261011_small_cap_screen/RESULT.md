# Q1441: cap 1 leads the small early-support screen

Early-target-support cap **1** produced the highest complete final-link
checks per counted field API entry among caps 1, 2, 4 and the prior cap-8
comparator on the frozen ordinary N53/N83 points. At N53 it checked 4,898
final links in 759,596 API entries, **1.52 times** cap 8's stage throughput.
At N83 it checked 2,535 links in 464,030 entries, **1.009 times** cap 8;
caps 1, 2, 4 and 8 are nearly tied there under this wall-capped protocol.
All exact S3 final-link tests in these rows rejected their candidate pair.

The curves and bases retain the project identifiers:
`EC1N53Ckb1hf77aab617904`, actual B=24,062, folded K=227, base digest
`05b75578ee58866bc8e5d3199cc77f441fa8649ccbaf88c089e998a00ea435e5`;
and `EC1N83Ckb1h876c2921cb64`, actual B=30,977,592, folded K=186,612,
base digest
`56c951ad78cc4036d3e8ff70bcb9d7feccacc6c763220b285def056cba30afb8`.
Both use the previously frozen ordinary point and `isogeny: "none"`.
`Q1441` is a PDP-stage proposal with `candidate_id: null` and
`run_id: null`.

## Fixed wall-cap screen

Fresh processes used the Q1437 executable with `seededpos` seed 2 at N53
and seed 8 at N83, `satpivot` pair roots, `selector` target support,
`eager` leaf checks, 5,000 conflicts, and 30 seconds. Q1440's cap-8 rows
are the matched comparator. Every row reached its wall cap and has status
`BOUNDED_UNKNOWN`. The exact input, source, binary, run, operation-vector
and raw-log receipts are in `measurements.json`.

| Field | Early cap | Final-link checks | Exact target S3 matches | Counted field API entries | Final checks per million entries |
| --- | ---: | ---: | ---: | ---: | ---: |
| N53 | **1** | 4,898 | 0 | 759,596 | **6,448** |
| N53 | 2 | 4,107 | 0 | 692,394 | 5,932 |
| N53 | 4 | 5,388 | 0 | 974,592 | 5,528 |
| N53 | 8 | 4,252 | 0 | 1,001,438 | 4,246 |
| N83 | **1** | 2,535 | 0 | 464,030 | **5,463** |
| N83 | 2 | 2,700 | 0 | 494,550 | 5,460 |
| N83 | 4 | 2,216 | 0 | 407,770 | 5,434 |
| N83 | 8 | 2,606 | 0 | 481,350 | 5,414 |

The N53 ranking is a useful stage lead. The N83 spread is less than 1%,
and wall-capped counts can shift with host contention. These are bounded
search diagnostics rather than controlled CPU speedups or a cost per
successful decomposition. The next comparison should stop at the same
fixed conflict count, with a generous wall safety cap, to remove the
different amount of solver work completed in 30 seconds.

## Cumulative work and verification

Every Q1437-Q1440 selection or policy attempt and all six Q1441 runs are
charged to the same point per field. The cumulative counted field API work
is **18,022,853** entries (\(2^{24.10}\)) at N53 and **5,228,258**
(\(2^{22.32}\)) at N83. The small-cap runs add no previously unseen
middle states to the earlier state unions of 146 and 206. Successful-query
work, verified relation yield and novel rank remain unmeasured under the
recorded caps.

`validate.py` passed executable, runner, prior-measurement and raw-log
hashes; exact schedules and caps; operation and cumulative state totals;
the cap-8 comparator; and 48 independent rejected-leaf trace checks. The
Q1437 executable's locked S3 controls passed independent replay.
`validation.json` records `PASS`.

The exact N131 W<=6 uniform-query supply bound permits less than
\(2^{33.36}\) abstract work units per ordinary query under a \(2^{61}\)
total cap with other costs zero. Counted API entries are a software event
unit and are not calibrated to that bound. The N131 fully charged \(2^x\)
projection and challenge gap remain null until successful-query work and
the remaining IC stages can be measured.

## Reproduction

After regenerating the frozen Q1430 CNF/maps and Q1432 targets and building
the Q1437 executable:

```sh
python3 experiments/compact-s3-m4-20261003/q20261011_small_cap_screen/run.py --binary /private/tmp/q1437_insearch
python3 experiments/compact-s3-m4-20261003/q20261011_small_cap_screen/validate.py --binary /private/tmp/q1437_insearch
```
