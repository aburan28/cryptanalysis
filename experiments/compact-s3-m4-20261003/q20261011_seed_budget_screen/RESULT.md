# Q1444: seed changes reach distinct middle states at equal N53 work

With early-support cap 1 and a 500,000-entry field API budget, N53 decision
seeds 2, 5 and 9 reached **three distinct checked middle states** on the
same frozen ordinary public point. The new seeds 5 and 9 each completed
about 3,110 distinct final-link checks at 500,098 and 500,044 counted
entries, matching seed 2's 3,110 checks at 500,068 entries. Seeds 5 and 9
checked row-4 middle states; seed 2 checked row 5. Thus the cap-1 throughput
persists across different parts of the middle-state search, while none of
these bounded searches produced an exact target S3 match.

N83 seeds 8, 10 and 14 also reached three distinct checked row-5 middle
states. The new seeds 10 and 14 reached the 180-second wall safety cap at
484,724 and 421,488 entries before their API budget, so they are censored
at different amounts of work. Their final-check rates remained near the
seed-8 rate of about 5,465 checks per million entries.

The curves, factor bases and workloads retain the project identifiers:
`EC1N53Ckb1hf77aab617904`, actual B=24,062, folded K=227, base digest
`05b75578ee58866bc8e5d3199cc77f441fa8649ccbaf88c089e998a00ea435e5`;
and `EC1N83Ckb1h876c2921cb64`, actual B=30,977,592, folded K=186,612,
base digest
`56c951ad78cc4036d3e8ff70bcb9d7feccacc6c763220b285def056cba30afb8`.
Each uses its frozen ordinary public point and `isogeny: "none"`.
`Q1444` is a PDP-stage proposal with `candidate_id: null` and
`run_id: null`.

## Frozen seed screen

The Q1443 executable, `seededpos` decision policy, cap-1 target support,
`satpivot` pair roots, `eager` leaf checks, 5,000-conflict limit, and
500,000-entry API budget were fixed. The only varied parameter was the
seed. A fresh solver process ran for each seed with no shared clauses.
The N53 seed 2 and N83 seed 8 baselines come from Q1443 with the same
binary and inputs; Q1444 added seeds 5 and 9 at N53 and 10 and 14 at N83.

| Field | Seed | Stop / status | Checked middle row | Complete final-link checks | Exact target S3 matches | API entries | Checks per million entries |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| N53 | 2 | API budget; `BOUNDED_UNKNOWN` | 5 | 3,110 | 0 | 500,068 | 6,219 |
| N53 | 5 | API budget; `BOUNDED_UNKNOWN` | 4 | 3,110 | 0 | 500,098 | 6,219 |
| N53 | 9 | API budget; `BOUNDED_UNKNOWN` | 4 | 3,109 | 0 | 500,044 | 6,217 |
| N83 | 8 | API budget; `BOUNDED_UNKNOWN` | 5 | 2,733 | 0 | 500,136 | 5,465 |
| N83 | 10 | 180 s wall; `BOUNDED_UNKNOWN` | 5 | 2,649 | 0 | 484,724 | 5,465 |
| N83 | 14 | 180 s wall; `BOUNDED_UNKNOWN` | 5 | 2,302 | 0 | 421,488 | 5,462 |

The N83 wall-capped rows are retained with their actual operation totals;
they are not equal-budget completions. CPU wall comparisons remain
exploratory on this host. Full source, binary, input, operation-vector,
status, memory and raw-log receipts are in `measurements.json`.

## Verification and challenge accounting

`validate.py` passed the source, binary, input and log hashes, exact
operation and stop records, cumulative charges, three distinct cap-1
middle states per field, and 32 independent rejected-leaf trace checks.
Q1443's locked N53/N83 controls passed independent three-link S3 replay
with the same executable. `validation.json` records `PASS`.

Charging all archived Q1437-Q1444 attempts on each single public point,
the cumulative work is **23,649,601** counted field API entries
(\(2^{24.50}\)) at N53 and **8,452,764** (\(2^{23.01}\)) at N83.
The Q1443 ledger also includes 49,328 entries from its two earlier
unfrozen N53 budget diagnostics. Successful-query work, verified relation
yield, novel rank, and the fully charged N131 \(2^x\) projection remain
unmeasured. The N131 W<=6 necessary affordability ceiling of less than
\(2^{33.36}\) abstract work units per ordinary query under a \(2^{61}\)
total cap uses a different unit from these API entries.

## Next solver step

The seed screen finds distinct middle states but nearly identical
final-check throughput and no exact target match within the recorded caps.
The next comparison should change the decomposition method rather than
only the seed: use the frozen N53/N83 points to compare this target-support
SAT search with a compact pair-index or guided meet-in-the-middle step at
a fixed operation boundary. Any complete S3 model must pass independent
curve-point, subgroup, factor-base and four-point-sum replay before its
cost enters a relation-yield estimate.

## Reproduction

After regenerating Q1430 CNF/maps and Q1432 targets and building Q1443's
executable:

```sh
python3 experiments/compact-s3-m4-20261003/q20261011_seed_budget_screen/run.py --binary /private/tmp/q1443_insearch
python3 experiments/compact-s3-m4-20261003/q20261011_seed_budget_screen/validate.py --binary /private/tmp/q1443_insearch
```
