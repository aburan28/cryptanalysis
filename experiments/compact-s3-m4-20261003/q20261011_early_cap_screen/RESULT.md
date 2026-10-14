# Q1440: cap 8 improves complete final-link checks per field API entry

At matched 30-second and 5,000-conflict limits on the frozen ordinary
N53/N83 public points, early-target-support cap **8** gave the highest
complete final-link checks per counted field API entry among caps 8, 25 and
128. At N53 it checked 4,252 final links in 1,001,438 entries, while cap
128 checked zero in 4,320,272 entries. At N83 cap 8 checked 2,606 links in
481,350 entries, **1.26 times** the final-check throughput of cap 128.
All checked final links in these runs were rejected by the exact S3 target
test; the metric measures search progress, not relation yield.

N53 is `EC1N53Ckb1hf77aab617904` with actual subgroup-usable factor-base
B=24,062 and folded K=227; N83 is `EC1N83Ckb1h876c2921cb64` with
B=30,977,592 and K=186,612. Their factor-base enumerated-set digests are
`05b75578ee58866bc8e5d3199cc77f441fa8649ccbaf88c089e998a00ea435e5`
and `56c951ad78cc4036d3e8ff70bcb9d7feccacc6c763220b285def056cba30afb8`.
The point, workload ID, factor base, and `isogeny: "none"` are the same as
Q1437-Q1439 within each field. `Q1440` is a PDP-stage proposal with
`candidate_id: null` and `run_id: null`.

## Matched cap comparison

Q1440 ran fresh cap-8 and cap-25 processes with the Q1437 executable,
`seededpos` seed 2 at N53 and seed 8 at N83. Q1438's cap-128 rows use the
same executable, seed, point, 30-second wall cap, 5,000-conflict cap,
`satpivot` S3 roots, `selector` target support, and `eager` leaf rationality.
Every row reached its wall cap and has status `BOUNDED_UNKNOWN`. Process and
solver time, per-method operation vectors, exact inputs, and raw logs are in
`measurements.json`. CPU wall ratios on this host are exploratory.

| Field | Early cap | Checked early states | Final-link checks | Target S3 matches | Field API entries | Final checks per million entries |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| N53 | **8** | 8 | 4,252 | 0 | 1,001,438 | **4,246** |
| N53 | 25 | 25 | 4,520 | 0 | 1,856,698 | 2,434 |
| N53 | 128 | 90 | 0 | 0 | 4,320,272 | 0 |
| N83 | **8** | 8 | 2,606 | 0 | 481,350 | **5,414** |
| N83 | 25 | 25 | 2,460 | 0 | 465,868 | 5,280 |
| N83 | 128 | 128 | 1,645 | 0 | 383,928 | 4,285 |

At N53 cap 8 performs 1.74 times as many final checks per entry as cap 25.
At N83 it performs 1.26 times as many as cap 128. Because the solver spends
different portions of a fixed wall cap in Python field calls and native SAT
search, checks per API entry is a bounded stage diagnostic rather than a
machine-independent cost of a successful query.

## Cumulative one-target work and verification

All Q1437-Q1439 selection and policy attempts plus the four Q1440 attempts
are charged to the same point per field. The cumulative work is
**15,596,271** counted API entries (\(2^{23.89}\)) at N53 and **3,861,908**
(\(2^{21.88}\)) at N83. The new cap rows add no previously unseen checked
middle state to the prior state unions of 146 and 206. Their contribution is
more complete final-link checks per counted entry. All four new attempts have
status `BOUNDED_UNKNOWN`; successful-query work, verified relation yield and
novel rank remain unmeasured.

`validate.py` passed the executable, runner, prior measurement and raw-log
hash checks; exact schedule/caps/statuses; all operation and cumulative
state totals; cap-128 comparator replay; and 32 independent rejected-leaf
trace checks. The Q1437 executable's locked controls passed independent S3
replay. `validation.json` records `PASS`.

The exact N131 W<=6 uniform-query supply bound leaves less than
\(2^{33.36}\) abstract work units per ordinary query under a \(2^{61}\)
total cap with other costs zero. Counted API entries are not calibrated to
those units, and a successful ordinary decomposition has not yet been
measured at N53 or N83. The N131 fully charged \(2^x\) projection and gap
remain null.

## Next parameter

Screen caps 1, 2 and 4 at the same frozen points and resource limits, using
complete final-link checks per counted entry as the stage objective. Then
allocate a longer fixed budget to the best cap on the known-satisfiable N53
ordinary point, keeping all failed attempts charged. If a complete S3 model
appears, replay its actual curve points, subgroup membership, factor-base
membership, and four-point sum independently before estimating successful
query cost.

## Reproduction

After generating the frozen Q1430 CNF/maps and Q1432 targets and building
the Q1437 executable:

```sh
python3 experiments/compact-s3-m4-20261003/q20261011_early_cap_screen/run.py --binary /private/tmp/q1437_insearch
python3 experiments/compact-s3-m4-20261003/q20261011_early_cap_screen/validate.py --binary /private/tmp/q1437_insearch
```
