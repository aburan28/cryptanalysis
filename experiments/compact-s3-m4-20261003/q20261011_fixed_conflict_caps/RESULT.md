# Q1442: the productive search phase sits between 50 and 65 conflicts

A 50-conflict stop ended all four frozen ordinary N53/N83 searches **before
any checked middle state**, after only 304 or 334 counted field API entries.
Raising the cap to 65 entered the productive phase, but all four runs then
reached a 90-second safety cap at 59–63 conflicts. This locates a sharp
search-cost transition and shows why a fixed conflict count does not make a
usable equal-work comparator here. In the longer bounded phase, cap 1 still
gave more complete final-link checks per counted API entry than cap 8 at
N53: 6,760 versus 4,062 per million. The N83 rates were nearly tied.

The frozen curves are `EC1N53Ckb1hf77aab617904` (actual B=24,062, folded
K=227, base digest
`05b75578ee58866bc8e5d3199cc77f441fa8649ccbaf88c089e998a00ea435e5`)
and `EC1N83Ckb1h876c2921cb64` (actual B=30,977,592, folded K=186,612,
base digest
`56c951ad78cc4036d3e8ff70bcb9d7feccacc6c763220b285def056cba30afb8`).
Each field uses the same frozen ordinary public point as Q1437-Q1441 and
`isogeny: "none"`. `Q1442` remains a PDP-stage proposal with
`candidate_id: null` and `run_id: null`.

## Frozen schedules and work

The unchanged Q1437 executable ran `seededpos` seed 2 at N53 and seed 8 at
N83, with early support caps 1 and 8, `satpivot` pair roots, `selector`
target support and `eager` rationality checks. Each attempt used a fresh
solver process and the same point within its field. The first schedule had
50 conflicts and a 60-second safety cap; the follow-up had 65 conflicts
and a 90-second safety cap. Every status was `BOUNDED_UNKNOWN`.

| Field | Early cap | Conflict / wall limit reached | Checked middle states | Final-link checks | Exact target S3 matches | Counted API entries | Final checks per million entries |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| N53 | 1 | 50 conflicts | 0 | 0 | 0 | 304 | 0 |
| N53 | 8 | 50 conflicts | 0 | 0 | 0 | 304 | 0 |
| N83 | 1 | 50 conflicts | 0 | 0 | 0 | 334 | 0 |
| N83 | 8 | 50 conflicts | 0 | 0 | 0 | 334 | 0 |
| N53 | 1 | 90 s; 61 conflicts | 1 | 17,847 | 0 | 2,639,958 | 6,760 |
| N53 | 8 | 90 s; 59 conflicts | 8 | 3,804 | 0 | 936,570 | 4,062 |
| N83 | 1 | 90 s; 62 conflicts | 1 | 4,465 | 0 | 816,284 | 5,470 |
| N83 | 8 | 90 s; 63 conflicts | 8 | 2,714 | 0 | 501,110 | 5,416 |

The 65-conflict rows did **not** reach the same conflict stop; their
checks-per-entry ratios remain bounded stage diagnostics. The host was
contended: the N53 cap-8 run completed fewer counted entries in 90 seconds
than its earlier 30-second run. CPU timing comparisons remain exploratory.
The exact method vectors, raw logs, input hashes, process and solver times,
caps and statuses are preserved in `measurements.json` and `followup.json`.

## Cumulative accounting and validation

All Q1437-Q1441 selected-seed, policy and cap attempts, plus both Q1442
schedules, are charged to the same public point in each field. The ledger
totals **21,599,989** counted field API entries (\(2^{24.36}\)) at N53
and **6,546,320** (\(2^{22.64}\)) at N83. The final-link checks above
produced no exact target S3 match within their recorded bounds. Successful
decomposition work, verified relation yield and novel rank remain
unmeasured.

`validate.py` passed source, binary, runner, prior-measurement and raw-log
hashes; all operation sums and cumulative charges; exact schedule, status
and stop checks; and 42 independent rejected-leaf trace calculations.
`validation.json` records `PASS`.

The N131 W<=6 necessary affordability ceiling is less than \(2^{33.36}\)
abstract work units per ordinary query under a \(2^{61}\) total cap when
other costs are zero. Field API entries are a different, uncalibrated unit.
The fully charged N131 \(2^x\) projection and challenge gap remain null.

## Next stop rule

Add a counted-API-entry budget to the external propagator, with a distinct
stop reason and exact counter receipt. Compare cap 1 against cap 8 at the
same API budget on N53 and N83. This directly fixes the amount of counted
arithmetic work and avoids the phase transition that defeats a conflict
stop. Preserve all censored rows and charge the operation-budget screen to
the same one-target ledger.

## Reproduction

After regenerating Q1430 inputs and Q1432 targets and building the Q1437
executable:

```sh
python3 experiments/compact-s3-m4-20261003/q20261011_fixed_conflict_caps/run.py --binary /private/tmp/q1437_insearch
python3 experiments/compact-s3-m4-20261003/q20261011_fixed_conflict_caps/run_followup.py --binary /private/tmp/q1437_insearch
python3 experiments/compact-s3-m4-20261003/q20261011_fixed_conflict_caps/validate.py --binary /private/tmp/q1437_insearch
```
