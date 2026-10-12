# Q1437: seeded restarts widen checked middle-state coverage

Sixteen fresh seeded searches on each frozen ordinary public point reached
**62 distinct checked middle states at N53** and **101 at N83**. The charged
four-summand PDP search used 4,881,904 (\(2^{22.22}\)) and 1,804,072
(\(2^{20.78}\)) counted field API method entries, respectively. All 32
attempts retained status `BOUNDED_UNKNOWN`; the totals include every bounded
attempt for the one target in each field.

The two curves are `EC1N53Ckb1hf77aab617904` and
`EC1N83Ckb1h876c2921cb64`. Their actual subgroup-usable factor-base sizes
before orbit folding are B=24,062 and B=30,977,592; their folded column
counts are K=227 and K=186,612. The enumerated-set digests are
`05b75578ee58866bc8e5d3199cc77f441fa8649ccbaf88c089e998a00ea435e5`
and `56c951ad78cc4036d3e8ff70bcb9d7feccacc6c763220b285def056cba30afb8`.
Both runs have `isogeny: "none"`. `Q1437` is a PDP-stage proposal;
`candidate_id` and `run_id` remain null because the complete IC pipeline is
not fixed or measured.

## Frozen method and measured work

The solver uses the Q1436 counted field and the compact chained-S3 encoding.
`seededpos` permutes the positive-first decision order over bits for each of
the six x-coordinate rows; seed parity chooses which leaf pair is visited
first. Seeds 0 through 15 run in order with a fresh CaDiCaL process and no
shared learned clauses. The same previously frozen ordinary public point is
used for all seeds within each field. `satpivot` pair roots, `selector` early
target support, and `eager` leaf rationality are fixed. Each attempt has a
500-conflict limit; wall limits are 5 s at N53 and 10 s at N83. Early support
is limited to 8 checked states per N53 run and 25 per N83 run.

| Field | Attempt statuses and limits reached | Total conflicts | Pair-root queries | Checked / distinct middle states | Final-link checks | Counted field API entries | Process wall across all attempts |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| N53 | 16 `BOUNDED_UNKNOWN`; 11 conflict, 5 wall | 5,822 | 7,082 | 62 / 62 | 8,649 | 4,881,904 (\(2^{22.22}\)) | 37.67 s |
| N83 | 16 `BOUNDED_UNKNOWN`; 13 conflict, 3 wall | 6,692 | 6,912 | 101 / 101 | 4,405 | 1,804,072 (\(2^{20.78}\)) | 60.88 s |

The search checked 12.70 distinct middle states per million API entries at
N53 and 55.98 at N83. The prior single `allpos` Q1436 runs checked one
state in 712,014 and 810,656 entries, respectively. The resulting coverage
per counted entry is 9.04 and 45.38 times those particular runs. These are
algorithmic search diagnostics across different conflict and wall budgets,
not paired CPU timing ratios or relation yields. The target state spaces and
the fraction that leads to a verified relation have not been measured by
these counts.

## Verification and challenge accounting

`validate.py` checks source and binary digests, all 32 raw-log hashes,
attempt ordering, status and cap records, exact operation-vector sums,
unique middle-state counts, and total charges. It independently replays 256
sampled nonrational-leaf trace decisions. Locked N53 seed 0 and N83 seed 1
controls each yield an S3 model that passes an independent three-link
evaluation. `validation.json` records `PASS` and the control log hashes.
The ordinary workload rows do not produce a completed relation under their
recorded caps, so successful-query work and novel-row rate remain unmeasured.

The exact N131 W<=6 uniform-query supply bound leaves less than
\(2^{33.36}\) abstract work units per ordinary query under a \(2^{61}\)
total cap when all other costs are set to zero. API method entries are a
software event unit and have not been calibrated to those abstract units.
The N131 fully charged \(2^x\) projection and gap to the challenge therefore
remain null. The next controlled allocation should deepen high-coverage
seed policies on the same N53 and N83 points, keep all failed attempts in the
one-target ledger, and seek an independently verified natural N53 relation
before fitting a successful-query exponent.

## Reproduction

Generate the Q1430 frozen CNF/maps and Q1432 target files as specified in
their experiment directories. From the repository root:

```sh
sh experiments/compact-s3-m4-20261003/q20261011_seeded_restart/build.sh /private/tmp/q1437_insearch
python3 experiments/compact-s3-m4-20261003/q20261011_seeded_restart/run_campaign.py --binary /private/tmp/q1437_insearch
python3 experiments/compact-s3-m4-20261003/q20261011_seeded_restart/validate.py --binary /private/tmp/q1437_insearch
```

`measurements.json` carries the exact curve, workload, factor-base, source,
binary, input, cap, status, process time, solver time, method-vector, and raw
log receipts. The native solver lives only in this experiment directory.
